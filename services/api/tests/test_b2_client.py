from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings, b2_s3_endpoint_url
from app.repo import b2_client
from main import REQUIRED_B2_SETTINGS

STANDARD_B2_ENV_NAMES = {
    "B2_REGION",
    "B2_APPLICATION_KEY_ID",
    "B2_APPLICATION_KEY",
    "B2_BUCKET_NAME",
    "B2_PUBLIC_URL_BASE",
}
REQUIRED_B2_ENV_NAMES = STANDARD_B2_ENV_NAMES - {"B2_PUBLIC_URL_BASE"}
LEGACY_B2_ENV_NAMES = {"B2_ENDPOINT", "B2_KEY_ID", "B2_S3_ENDPOINT"}


def test_required_b2_settings_use_standard_env_names():
    assert {env_name for _, env_name in REQUIRED_B2_SETTINGS} == REQUIRED_B2_ENV_NAMES


def test_env_example_only_uses_standard_b2_env_names():
    repo_root = Path(__file__).resolve().parents[3]
    env_keys = []
    for raw_line in (repo_root / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key.startswith("B2_"):
            env_keys.append(key)

    assert set(env_keys) == STANDARD_B2_ENV_NAMES
    assert len(env_keys) == len(set(env_keys))
    assert not LEGACY_B2_ENV_NAMES.intersection(env_keys)


def test_b2_region_derives_endpoint_for_valid_region():
    assert b2_s3_endpoint_url("us-west-004") == "https://s3.us-west-004.backblazeb2.com"
    assert Settings(b2_region="eu-central-003", _env_file=None).b2_region == "eu-central-003"


@pytest.mark.parametrize(
    "payload",
    [
        "attacker.example/collect",
        "us-west-004:443/path",
        "us-west-004?x=",
    ],
)
def test_b2_region_rejects_url_metacharacters(payload):
    with pytest.raises(ValueError, match="B2_REGION"):
        b2_s3_endpoint_url(payload)

    with pytest.raises(ValidationError):
        Settings(b2_region=payload, _env_file=None)


def test_object_key_prefix_uses_non_b2_env_name(monkeypatch):
    monkeypatch.setenv("B2_KEY_PREFIX", "legacy-prefix/")
    monkeypatch.delenv("OBJECT_KEY_PREFIX", raising=False)

    assert Settings(_env_file=None).object_key_prefix == "arxiv-insight-briefs/"

    monkeypatch.setenv("OBJECT_KEY_PREFIX", "custom-prefix/")

    assert Settings(_env_file=None).object_key_prefix == "custom-prefix/"


def test_b2_client_honors_object_key_prefix(monkeypatch):
    monkeypatch.setattr(b2_client.settings, "object_key_prefix", "custom-prefix/")

    assert b2_client._full_key("papers/1234.5678.pdf") == "custom-prefix/papers/1234.5678.pdf"
    assert b2_client._strip_prefix("custom-prefix/papers/1234.5678.pdf") == "papers/1234.5678.pdf"


def test_get_s3_client_uses_derived_endpoint_and_custom_user_agent(monkeypatch):
    b2_client.get_s3_client.cache_clear()
    monkeypatch.setattr(b2_client.settings, "b2_region", "us-west-004")
    monkeypatch.setattr(b2_client.settings, "b2_application_key_id", "test-key-id")
    monkeypatch.setattr(b2_client.settings, "b2_application_key", "test-application-key")

    captured: dict = {}
    sentinel = object()

    def fake_client(service_name: str, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(b2_client.boto3, "client", fake_client)

    assert b2_client.get_s3_client() is sentinel

    assert captured["service_name"] == "s3"
    assert captured["endpoint_url"] == "https://s3.us-west-004.backblazeb2.com"
    assert captured["region_name"] == "us-west-004"
    assert captured["aws_access_key_id"] == "test-key-id"
    assert captured["aws_secret_access_key"] == "test-application-key"
    assert "(backblaze-b2-samples)" in captured["config"].user_agent_extra

    b2_client.get_s3_client.cache_clear()
