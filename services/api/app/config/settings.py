import os
import re

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

B2_REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-[a-z]+){1,2}-\d{3}$")
DEFAULT_OBJECT_KEY_PREFIX = "arxiv-insight-briefs/"
OBJECT_KEY_PREFIX_ENV = "OBJECT_KEY_PREFIX"
LEGACY_OBJECT_KEY_PREFIX_ENV = "B2_KEY_PREFIX"


def validate_b2_region(region: str) -> str:
    if not B2_REGION_PATTERN.fullmatch(region):
        raise ValueError("B2_REGION must be a Backblaze region slug")
    return region


def b2_s3_endpoint_url(region: str) -> str:
    return f"https://s3.{validate_b2_region(region)}.backblazeb2.com"


def default_object_key_prefix() -> str:
    return os.getenv(LEGACY_OBJECT_KEY_PREFIX_ENV, DEFAULT_OBJECT_KEY_PREFIX)


class Settings(BaseSettings):
    # --- Backblaze B2 (required) ---
    # Standardized env-var names per the sample quality-keeper checks.
    # Defaults are empty so test collection never raises; lifespan validates at startup.
    b2_region: str = ""
    b2_application_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    b2_public_url_base: str = ""

    # Object-key prefix inside the bucket — keeps this sample isolated if the
    # bucket is shared with other tools. Override per-deployment if desired.
    object_key_prefix: str = Field(default_factory=default_object_key_prefix)

    # --- API ---
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000,http://localhost:3001"
    api_cors_origin_regex: str = ""

    # --- NVIDIA Build (optional — graceful degrade when missing) ---
    # Free-tier inference at https://build.nvidia.com. If unset, the pipeline
    # skips router + synthesis stages and surfaces a "done_no_analysis" brief.
    nvidia_api_key: str = ""
    nvidia_nemotron_model: str = "mistralai/mistral-nemotron"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    # --- Briefing pipeline tuning ---
    arxiv_candidate_limit: int = 50
    brief_paper_limit: int = 8
    brief_time_window_months: int = 12
    # Soft cap on concurrent briefings to keep the demo predictable.
    max_briefs_in_flight: int = 2
    # Per-paper character cap fed to the synthesis LLM call. Section-trim is
    # a soft heuristic; this is the hard ceiling.
    max_paper_chars: int = 12_000
    # Presigned URL TTL for per-citation PDF links surfaced in the UI.
    presigned_ttl_seconds: int = 3600

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @field_validator("b2_region")
    @classmethod
    def validate_region(cls, region: str) -> str:
        if not region:
            return region
        return validate_b2_region(region)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]


settings = Settings()
