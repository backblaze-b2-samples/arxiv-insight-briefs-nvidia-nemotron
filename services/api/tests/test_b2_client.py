import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
from pydantic import ValidationError

from app.config import Settings, b2_s3_endpoint_url
from app.repo import b2_client
from main import REQUIRED_B2_SETTINGS, app, lifespan

STANDARD_B2_ENV_NAMES = {
    "B2_REGION",
    "B2_APPLICATION_KEY_ID",
    "B2_APPLICATION_KEY",
    "B2_BUCKET_NAME",
    "B2_PUBLIC_URL_BASE",
}
REQUIRED_B2_ENV_NAMES = STANDARD_B2_ENV_NAMES - {"B2_PUBLIC_URL_BASE"}
LEGACY_REQUIRED_B2_ENV_NAMES = {"B2_ENDPOINT", "B2_KEY_ID", "B2_S3_ENDPOINT"}
LEGACY_PREFIX_ENV_NAME = "B2_KEY_PREFIX"
OBJECT_PREFIX_ENV_NAME = "OBJECT_KEY_PREFIX"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def env_example_keys() -> list[str]:
    env_keys = []
    for raw_line in (repo_root() / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        env_keys.append(line.split("=", 1)[0].strip())
    return env_keys


def js_string_array(name: str) -> set[str]:
    script = (repo_root() / "scripts/doctor.mjs").read_text(encoding="utf-8")
    match = re.search(rf"const {name} = \[(.*?)\];", script, flags=re.DOTALL)
    assert match is not None
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def test_required_b2_settings_use_standard_env_names():
    assert {env_name for _, env_name in REQUIRED_B2_SETTINGS} == REQUIRED_B2_ENV_NAMES


def test_env_contract_matches_exported_setup_surfaces():
    env_keys = env_example_keys()
    b2_env_keys = [key for key in env_keys if key.startswith("B2_")]

    assert set(b2_env_keys) == STANDARD_B2_ENV_NAMES
    assert len(b2_env_keys) == len(set(b2_env_keys))
    assert not LEGACY_REQUIRED_B2_ENV_NAMES.intersection(b2_env_keys)
    assert LEGACY_PREFIX_ENV_NAME not in env_keys
    assert OBJECT_PREFIX_ENV_NAME in env_keys

    assert js_string_array("REQUIRED_B2_VARS") == REQUIRED_B2_ENV_NAMES
    assert js_string_array("LEGACY_REQUIRED_B2_VARS") == LEGACY_REQUIRED_B2_ENV_NAMES
    assert f'const LEGACY_PREFIX_VAR = "{LEGACY_PREFIX_ENV_NAME}"' in (
        repo_root() / "scripts/doctor.mjs"
    ).read_text(encoding="utf-8")

    assert set(Settings.model_fields) >= {
        "b2_region",
        "b2_application_key_id",
        "b2_application_key",
        "b2_bucket_name",
        "b2_public_url_base",
        "object_key_prefix",
    }
    assert "b2_key_prefix" not in Settings.model_fields


def test_b2_region_derives_endpoint_for_valid_region():
    assert b2_s3_endpoint_url("us-test-000") == "https://s3.us-test-000.backblazeb2.com"
    assert Settings(b2_region="us-test-000", _env_file=None).b2_region == "us-test-000"


@pytest.mark.parametrize(
    "payload",
    [
        "attacker.example/collect",
        "attacker.example/#",
        "attacker.example?x=",
        "attacker.example/%2e%2e",
        "us-test-000:443/path",
        "us-test-000?x=",
        " us-test-000",
        "us-test-000 ",
        "//attacker.example",
        "user@attacker.example",
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

    assert Settings(_env_file=None).object_key_prefix == "legacy-prefix/"

    monkeypatch.setenv("OBJECT_KEY_PREFIX", "custom-prefix/")

    assert Settings(_env_file=None).object_key_prefix == "custom-prefix/"


@pytest.mark.asyncio
async def test_lifespan_warns_for_legacy_object_key_prefix(monkeypatch, caplog):
    monkeypatch.setenv("B2_KEY_PREFIX", "legacy-prefix/")
    monkeypatch.delenv("OBJECT_KEY_PREFIX", raising=False)

    with caplog.at_level(logging.WARNING, logger="api"):
        async with lifespan(app):
            pass

    assert "B2_KEY_PREFIX is deprecated; rename it to OBJECT_KEY_PREFIX" in caplog.text


def test_b2_public_url_base_is_optional(monkeypatch):
    monkeypatch.delenv("B2_PUBLIC_URL_BASE", raising=False)

    loaded = Settings(_env_file=None)

    assert loaded.b2_public_url_base == ""
    assert "B2_PUBLIC_URL_BASE" not in {env_name for _, env_name in REQUIRED_B2_SETTINGS}


def test_b2_client_honors_object_key_prefix(monkeypatch):
    monkeypatch.setattr(b2_client.settings, "object_key_prefix", "custom-prefix/")

    assert b2_client._full_key("papers/1234.5678.pdf") == "custom-prefix/papers/1234.5678.pdf"
    assert b2_client._strip_prefix("custom-prefix/papers/1234.5678.pdf") == "papers/1234.5678.pdf"


def test_get_s3_client_uses_derived_endpoint_and_custom_user_agent(monkeypatch):
    b2_client.get_s3_client.cache_clear()
    monkeypatch.setattr(b2_client.settings, "b2_region", "us-test-000")
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
    assert captured["endpoint_url"] == "https://s3.us-test-000.backblazeb2.com"
    assert urlparse(captured["endpoint_url"]).hostname == "s3.us-test-000.backblazeb2.com"
    assert captured["region_name"] == "us-test-000"
    assert captured["aws_access_key_id"] == "test-key-id"
    assert captured["aws_secret_access_key"] == "test-application-key"
    assert "(backblaze-b2-samples)" in captured["config"].user_agent_extra

    b2_client.get_s3_client.cache_clear()


@pytest.mark.parametrize(
    "payload",
    [
        "attacker.example/#",
        "attacker.example?x=",
        "attacker.example/%2e%2e",
        " us-test-000",
        "//attacker.example",
    ],
)
def test_get_s3_client_rejects_malformed_region_before_boto(monkeypatch, payload):
    b2_client.get_s3_client.cache_clear()
    monkeypatch.setattr(b2_client.settings, "b2_region", payload)

    def fail_client(*_args, **_kwargs):
        raise AssertionError("boto3.client should not be called")

    monkeypatch.setattr(b2_client.boto3, "client", fail_client)

    with pytest.raises(ValueError, match="B2_REGION"):
        b2_client.get_s3_client()

    b2_client.get_s3_client.cache_clear()
