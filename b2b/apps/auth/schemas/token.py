from uuid import UUID

from pydantic import BaseModel

from apps.auth.enums import UserRole


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
    id: UUID
    role: UserRole
