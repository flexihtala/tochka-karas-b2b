from uuid import UUID

from pydantic import BaseModel, Field

from shared.auth_lib import UserRole


class AuthTokensResponseSchema(BaseModel):
    """Ответ POST /auth/login. Соответствует TokenResponse из neomarket-moderation.yaml."""

    user_id: UUID
    access_token: str
    refresh_token: str
    token_type: str = Field(default='Bearer')
    expires_in: int
    role: UserRole


class RefreshTokensResponseSchema(BaseModel):
    """Ответ POST /auth/refresh. user_id опционален — endpoints не всегда его возвращают."""

    user_id: UUID
    access_token: str
    refresh_token: str
    token_type: str = Field(default='Bearer')
    expires_in: int
    role: UserRole


class ErrorResponseSchema(BaseModel):
    code: str
    message: str
