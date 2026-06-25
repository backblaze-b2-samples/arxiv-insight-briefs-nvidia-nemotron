"""B2 S3 data-access layer.

All boto3 / botocore usage is contained here; structural test
`tests/test_structure.py::test_boto3_only_in_repo` enforces it.
"""

import functools
import io
from datetime import UTC, datetime
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import b2_s3_endpoint_url, settings

# App identity used for the custom user agent. Bumped manually; do not source
# from pyproject.toml at import time (avoids the dependency).
APP_SLUG = "arxiv-insight-briefs"
APP_VERSION = "0.1.0"


def _s3_endpoint_url() -> str:
    return b2_s3_endpoint_url(settings.b2_region)


@functools.lru_cache(maxsize=1)
def get_s3_client():
    """Module-level singleton — boto3 maintains its own HTTP connection pool."""
    return boto3.client(
        "s3",
        endpoint_url=_s3_endpoint_url(),
        region_name=settings.b2_region,
        aws_access_key_id=settings.b2_application_key_id,
        aws_secret_access_key=settings.b2_application_key,
        config=Config(
            signature_version="s3v4",
            user_agent_extra=f"{APP_SLUG}/{APP_VERSION} (backblaze-b2-samples)",
        ),
    )


def _full_key(key: str) -> str:
    """Prepend the sample-level key prefix (keeps the bucket shareable)."""
    prefix = settings.object_key_prefix
    if prefix and not key.startswith(prefix):
        return prefix + key
    return key


def _strip_prefix(key: str) -> str:
    prefix = settings.object_key_prefix
    if prefix and key.startswith(prefix):
        return key[len(prefix):]
    return key


def check_connectivity() -> bool:
    """Cheap reachability probe used by /health. Never raises."""
    try:
        client = get_s3_client()
        client.head_bucket(Bucket=settings.b2_bucket_name)
        return True
    except Exception:
        return False


def head_object_or_none(key: str) -> dict | None:
    """Return S3 HeadObject response, or None if the key is missing.

    Used as a cache check (e.g. before re-downloading a PDF). Re-raises on
    non-404 errors so genuine S3 failures aren't swallowed.
    """
    client = get_s3_client()
    try:
        return client.head_object(Bucket=settings.b2_bucket_name, Key=_full_key(key))
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return None
        raise


def object_exists(key: str) -> bool:
    return head_object_or_none(key) is not None


def put_bytes(key: str, body: bytes, content_type: str = "application/octet-stream") -> None:
    """Write raw bytes to B2 at `key`. Raises RuntimeError on failure."""
    client = get_s3_client()
    try:
        client.put_object(
            Bucket=settings.b2_bucket_name,
            Key=_full_key(key),
            Body=io.BytesIO(body),
            ContentType=content_type,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 put failed for '{key}': {e}") from e


def put_text(key: str, body: str, content_type: str = "text/plain; charset=utf-8") -> None:
    put_bytes(key, body.encode("utf-8"), content_type=content_type)


def get_bytes(key: str) -> bytes:
    """Read an object back as raw bytes. Raises if missing — callers should
    HEAD first when a miss is expected (see pdf_pipeline)."""
    client = get_s3_client()
    try:
        resp = client.get_object(Bucket=settings.b2_bucket_name, Key=_full_key(key))
    except ClientError as e:
        raise RuntimeError(f"B2 get failed for '{key}': {e}") from e
    return resp["Body"].read()


def get_text(key: str) -> str:
    return get_bytes(key).decode("utf-8")


def list_prefix(prefix: str, max_keys: int = 1000) -> list[dict]:
    """Return S3 object summaries (key, size, last_modified) under prefix.

    Paginates correctly — list_objects_v2 is hard-capped at 1000 per call.
    """
    client = get_s3_client()
    items: list[dict] = []
    kwargs: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": _full_key(prefix),
        "MaxKeys": min(1000, max_keys),
    }
    try:
        while len(items) < max_keys:
            response = client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                items.append(
                    {
                        "key": _strip_prefix(obj["Key"]),
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                    }
                )
                if len(items) >= max_keys:
                    break
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 list failed for '{prefix}': {e}") from e
    return items


def delete_object(key: str) -> None:
    client = get_s3_client()
    try:
        client.delete_object(Bucket=settings.b2_bucket_name, Key=_full_key(key))
    except ClientError as e:
        raise RuntimeError(f"B2 delete failed for '{key}': {e}") from e


def delete_prefix(prefix: str) -> int:
    """Delete all objects under prefix. Returns the number deleted.

    Used by the "clear cached briefings" admin action. Never call with an
    empty prefix — refuses to operate at the bucket root.
    """
    if not prefix or prefix in ("/", settings.object_key_prefix):
        raise ValueError("delete_prefix refuses to operate at the bucket root")
    client = get_s3_client()
    deleted = 0
    items = list_prefix(prefix, max_keys=10_000)
    if not items:
        return 0
    # delete_objects caps at 1000 keys per call.
    batch: list[dict] = []
    for item in items:
        batch.append({"Key": _full_key(item["key"])})
        if len(batch) == 1000:
            client.delete_objects(Bucket=settings.b2_bucket_name, Delete={"Objects": batch})
            deleted += len(batch)
            batch = []
    if batch:
        client.delete_objects(Bucket=settings.b2_bucket_name, Delete={"Objects": batch})
        deleted += len(batch)
    return deleted


def presign_get(key: str, expires_in: int | None = None, filename: str | None = None) -> str:
    """Generate a presigned GET URL. `filename` triggers an attachment disposition."""
    client = get_s3_client()
    ttl = expires_in or settings.presigned_ttl_seconds
    params: dict = {"Bucket": settings.b2_bucket_name, "Key": _full_key(key)}
    if filename:
        encoded = quote(filename, safe="")
        params["ResponseContentDisposition"] = (
            f"attachment; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"
        )
    try:
        return client.generate_presigned_url("get_object", Params=params, ExpiresIn=ttl)
    except ClientError as e:
        raise RuntimeError(f"B2 presign failed for '{key}': {e}") from e


def now_utc() -> datetime:
    """Single timezone-aware clock for the repo layer."""
    return datetime.now(UTC)
