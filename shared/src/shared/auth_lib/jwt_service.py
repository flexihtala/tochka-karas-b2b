import uuid
from datetime import UTC, datetime, timedelta

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from shared.auth_lib.enums import UserRole
from shared.auth_lib.protocols import AuthSettingsProtocol
from shared.auth_lib.schemas import IssuedTokenSchema, JwtClaimsSchema, TokenPairSchema


class JwtInvalidError(Exception):
    pass


class JwtExpiredError(Exception):
    pass


class JwtService:
    """JWT issuer/decoder. HS256 default; supports asymmetric via private/public keys."""

    def __init__(self, settings: AuthSettingsProtocol):
        self.settings = settings

    def issue_token_pair(self, user_id: uuid.UUID, role: UserRole) -> TokenPairSchema:
        return TokenPairSchema(
            access=self.issue_token(user_id, role, self.settings.access_token_ttl_seconds),
            refresh=self.issue_token(user_id, role, self.settings.refresh_token_ttl_seconds),
        )

    def issue_token(self, user_id: uuid.UUID, role: UserRole, ttl_seconds: int) -> IssuedTokenSchema:
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds)
        claims = JwtClaimsSchema(
            sub=user_id,
            role=role,
            iat=int(now.timestamp()),
            exp=int(expires_at.timestamp()),
            jti=uuid.uuid4(),
        )
        token = jwt.encode(
            payload={
                'sub': str(claims.sub),
                'role': claims.role.value,
                'iat': claims.iat,
                'exp': claims.exp,
                'jti': str(claims.jti),
            },
            key=self._signing_key,
            algorithm=self.settings.jwt_algorithm,
        )
        return IssuedTokenSchema(value=token, claims=claims)

    def decode(self, token: str) -> JwtClaimsSchema:
        try:
            payload = jwt.decode(
                token,
                key=self._verification_key,
                algorithms=[self.settings.jwt_algorithm],
            )
        except ExpiredSignatureError as exc:
            raise JwtExpiredError from exc
        except InvalidTokenError as exc:
            raise JwtInvalidError from exc

        try:
            return JwtClaimsSchema.model_validate(payload)
        except ValueError as exc:
            raise JwtInvalidError from exc

    @property
    def _signing_key(self) -> str:
        if self.settings.jwt_algorithm == 'HS256':
            return self.settings.jwt_secret
        if self.settings.jwt_private_key:
            return self.settings.jwt_private_key
        raise JwtInvalidError('JWT_PRIVATE_KEY is required for asymmetric signing')

    @property
    def _verification_key(self) -> str:
        if self.settings.jwt_algorithm == 'HS256':
            return self.settings.jwt_secret
        if self.settings.jwt_public_key:
            return self.settings.jwt_public_key
        raise JwtInvalidError('JWT_PUBLIC_KEY is required for asymmetric verification')
