from pathlib import Path

from app.repo import b2_client
from main import REQUIRED_B2_SETTINGS


def test_required_b2_settings_use_standard_env_names():
    assert tuple(env_name for _, env_name in REQUIRED_B2_SETTINGS) == (
        "B2_REGION",
        "B2_APPLICATION_KEY_ID",
        "B2_APPLICATION_KEY",
        "B2_BUCKET_NAME",
        "B2_PUBLIC_URL_BASE",
    )


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

    assert tuple(env_keys) == (
        "B2_REGION",
        "B2_APPLICATION_KEY_ID",
        "B2_APPLICATION_KEY",
        "B2_BUCKET_NAME",
        "B2_PUBLIC_URL_BASE",
    )


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
    assert captured["region_name"] == "us-test-000"
    assert captured["aws_access_key_id"] == "test-key-id"
    assert captured["aws_secret_access_key"] == "test-application-key"
    assert "(backblaze-b2-samples)" in captured["config"].user_agent_extra

    b2_client.get_s3_client.cache_clear()
