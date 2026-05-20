from typing import Protocol


class AuthSettingsProtocol(Protocol):
    """Минимум, что должен иметь сервисный Settings для работы с shared/auth_lib."""

    jwt_algorithm: str
    jwt_secret: str
    jwt_private_key: str | None
    jwt_public_key: str | None
    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int
