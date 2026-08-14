"""
backend/config.py — environment-driven settings for the FastAPI service.

Replaces Streamlit's st.secrets with plain environment variables, so the
backend has no dependency on Streamlit at all. See MIGRATION.md for the
full list of variables and how they map to the old secrets.toml sections.
"""
import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent / ".env"


class AuthUser(dict):
    """username / bcrypt password_hash / role, loaded from AUTH_USERS_JSON."""
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # ── Supabase ──
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_key: str = Field(default="", alias="SUPABASE_SERVICE_KEY")

    # ── Gemini ──
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # ── Auth ──
    jwt_secret: str = Field(default="", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 7
    # JSON array: [{"username": "...", "password_hash": "$2b$...", "role": "admin"}]
    auth_users_json: str = Field(default="[]", alias="AUTH_USERS_JSON")

    # ── CORS ──
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    # ── Upload guards ──
    max_upload_mb: int = 20
    max_upload_rows: int = 200_000

    @property
    def auth_users(self) -> list[dict]:
        try:
            return json.loads(self.auth_users_json)
        except (TypeError, ValueError):
            return []

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
