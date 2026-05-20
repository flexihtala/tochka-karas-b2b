from uuid import UUID

from pydantic import BaseModel

from shared.auth_lib.enums import UserRole


class JwtClaimsSchema(BaseModel):
    sub: UUID
    role: UserRole
    iat: int
    exp: int
    jti: UUID


class IssuedTokenSchema(BaseModel):
    value: str
    claims: JwtClaimsSchema


class TokenPairSchema(BaseModel):
    access: IssuedTokenSchema
    refresh: IssuedTokenSchema


class AuthenticatedUserSchema(BaseModel):
    """Минимум, что middleware кладёт в request.state.user после декода JWT."""

    id: UUID
    role: UserRole
