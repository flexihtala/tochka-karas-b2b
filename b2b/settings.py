from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    database_url: str = Field(
        default='postgresql+asyncpg://postgres:postgres@localhost:5433/b2b',
        alias='DATABASE_URL',
    )
    jwt_algorithm: str = Field(default='HS256', alias='JWT_ALGORITHM')
    jwt_secret: str = Field(default='dev-secret-change-me-at-least-32-bytes', alias='JWT_SECRET')
    jwt_private_key: str | None = Field(default=None, alias='JWT_PRIVATE_KEY')
    jwt_public_key: str | None = Field(default=None, alias='JWT_PUBLIC_KEY')
    access_token_ttl_seconds: int = Field(default=3600, alias='ACCESS_TOKEN_TTL_SECONDS')
    refresh_token_ttl_seconds: int = Field(default=2_592_000, alias='REFRESH_TOKEN_TTL_SECONDS')

    # Service-to-service ключи. b2c_to_b2b_key используется в /inventory/* endpoints.
    b2c_to_b2b_key: str = Field(default='dev-b2c-to-b2b-key-change-me', alias='B2C_TO_B2B_KEY')

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace('+asyncpg', '+psycopg2')


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
