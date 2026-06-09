from uuid import UUID

from pydantic import BaseModel, Field


class AuthTokensResponseSchema(BaseModel):
    user_id: UUID
    access_token: str
    refresh_token: str
    token_type: str = Field(default='Bearer')
    expires_in: int


class RefreshTokensResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = Field(default='Bearer')
    expires_in: int


class ErrorResponseSchema(BaseModel):
    code: str
    message: str
