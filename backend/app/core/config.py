from typing import Literal

from pydantic import AnyHttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: SecretStr
    frontend_url: AnyHttpUrl = AnyHttpUrl("http://localhost:3000")
    backend_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000")
    environment: Literal["development", "test", "production"] = "development"
    github_client_id: str
    github_client_secret: SecretStr
    github_app_id: str | None = None
    github_app_private_key: SecretStr | None = None
    github_app_slug: str | None = None
    github_callback_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000/api/auth/github/callback")
    session_secret: SecretStr
    admin_github_logins: str = "imjakeym8,markschwart34"
    session_max_age_seconds: int = 28_800
    storage_bucket: str | None = None
    storage_endpoint: AnyHttpUrl | None = None
    storage_region: str = "us-east-1"
    storage_access_key: SecretStr | None = None
    storage_secret_key: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            if url.drivername not in {"postgresql", "postgresql+asyncpg"} or not url.database:
                raise ValueError
        except Exception as error:
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL URL with a database name"
            ) from error
        return SecretStr(
            url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
        )

    @field_validator("frontend_url", "backend_url")
    @classmethod
    def validate_origin(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.path not in {None, "/"} or value.query or value.fragment or value.username:
            raise ValueError("Origin URLs must not contain a path, query, fragment, or credentials")
        return value

    @field_validator("github_client_id")
    @classmethod
    def validate_client_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("GITHUB_CLIENT_ID must not be empty")
        return value.strip()

    @field_validator("github_client_secret", "session_secret")
    @classmethod
    def validate_secrets(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("OAuth and session secrets must be at least 32 characters")
        return value

    @field_validator("session_max_age_seconds")
    @classmethod
    def validate_session_max_age(cls, value: int) -> int:
        if not 300 <= value <= 2_592_000:
            raise ValueError("SESSION_MAX_AGE_SECONDS must be between 300 and 2592000")
        return value

    @field_validator("admin_github_logins")
    @classmethod
    def normalize_admin_logins(cls, value: str) -> str:
        logins = sorted({login.strip().casefold() for login in value.split(",") if login.strip()})
        if not logins:
            raise ValueError("ADMIN_GITHUB_LOGINS must contain at least one GitHub login")
        return ",".join(logins)

    @model_validator(mode="after")
    def validate_production_transport(self) -> "Settings":
        expected_callback = f"{str(self.backend_url).rstrip('/')}/api/auth/github/callback"
        if str(self.github_callback_url) != expected_callback:
            raise ValueError("GITHUB_CALLBACK_URL must use BACKEND_URL and the OAuth callback path")
        if self.environment == "production":
            urls = (self.frontend_url, self.backend_url, self.github_callback_url)
            if any(url.scheme != "https" for url in urls):
                raise ValueError("Production frontend, backend, and callback URLs must use HTTPS")
        storage_values = (
            self.storage_bucket.strip() if self.storage_bucket else "",
            self.storage_access_key.get_secret_value().strip() if self.storage_access_key else "",
            self.storage_secret_key.get_secret_value().strip() if self.storage_secret_key else "",
        )
        if any(storage_values) and not all(storage_values):
            raise ValueError(
                "Storage bucket, access key, and secret key must be configured together"
            )
        return self

    @property
    def storage_is_configured(self) -> bool:
        return bool(
            self.storage_bucket
            and self.storage_access_key
            and self.storage_secret_key
            and self.storage_bucket.strip()
            and self.storage_access_key.get_secret_value().strip()
            and self.storage_secret_key.get_secret_value().strip()
        )

    @property
    def github_app_is_configured(self) -> bool:
        return bool(
            self.github_app_id
            and self.github_app_private_key
            and self.github_app_id.strip()
            and self.github_app_private_key.get_secret_value().strip()
        )

    @property
    def allowed_admin_logins(self) -> frozenset[str]:
        return frozenset(self.admin_github_logins.split(","))
