from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModerationSettings(BaseSettings):
    """Settings для сервиса Moderation. Изолированы от b2b (свой database_url, свой контейнер)."""

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    database_url: str = Field(
        default='postgresql+asyncpg://postgres:postgres@localhost:5434/moderation',
        alias='DATABASE_URL',
    )
    jwt_algorithm: str = Field(default='HS256', alias='JWT_ALGORITHM')
    jwt_secret: str = Field(default='dev-secret-change-me-at-least-32-bytes', alias='JWT_SECRET')
    jwt_private_key: str | None = Field(default=None, alias='JWT_PRIVATE_KEY')
    jwt_public_key: str | None = Field(default=None, alias='JWT_PUBLIC_KEY')
    access_token_ttl_seconds: int = Field(default=3600, alias='ACCESS_TOKEN_TTL_SECONDS')
    refresh_token_ttl_seconds: int = Field(default=2_592_000, alias='REFRESH_TOKEN_TTL_SECONDS')

    # Service-to-service auth: ключи, которыми принимаем callback'и от b2b.
    b2b_to_mod_key: str = Field(default='dev-b2b-to-mod-key-change-me', alias='B2B_TO_MOD_KEY')
    mod_to_b2b_key: str = Field(default='dev-mod-to-b2b-key-change-me', alias='MOD_TO_B2B_KEY')
    # Base URL of the B2B service — moderation talks to B2B only via API (own DB).
    b2b_url: str = Field(default='http://localhost:8001', alias='B2B_URL')

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace('+asyncpg', '+psycopg2')


@lru_cache
def get_settings() -> ModerationSettings:
    return ModerationSettings()


settings = get_settings()
