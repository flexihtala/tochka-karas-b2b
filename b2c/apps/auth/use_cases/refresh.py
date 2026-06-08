from datetime import UTC, datetime

from apps.auth.errors import InvalidTokenError, TokenExpiredError, TokenRevokedError, UserBlockedError
from apps.auth.repositories import RefreshBlacklistRepository, RefreshTokenRepository, UserRepository
from apps.auth.schemas.refresh_blacklist import RefreshBlacklistCreateSchema
from apps.auth.schemas.refresh_token import RefreshTokenCreateSchema
from apps.auth.schemas.request import RefreshRequestSchema
from apps.auth.schemas.response import RefreshTokensResponseSchema
from settings import B2CSettings
from shared.auth_lib import JwtExpiredError, JwtInvalidError, JwtService


class RefreshUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        refresh_token_repository: RefreshTokenRepository,
        refresh_blacklist_repository: RefreshBlacklistRepository,
        jwt_service: JwtService,
        settings: B2CSettings,
    ):
        self.user_repository = user_repository
        self.refresh_token_repository = refresh_token_repository
        self.refresh_blacklist_repository = refresh_blacklist_repository
        self.jwt_service = jwt_service
        self.settings = settings

    async def __call__(self, data: RefreshRequestSchema) -> RefreshTokensResponseSchema:
        claims = self._decode_refresh_token(data.refresh_token)

        if await self.refresh_blacklist_repository.exists(claims.jti):
            raise TokenRevokedError()

        active_refresh = await self.refresh_token_repository.get_by_jti(claims.jti)
        if active_refresh is None:
            raise TokenRevokedError()

        user = await self.user_repository.get_or_none(claims.sub)
        if user is None:
            raise TokenRevokedError()
        if not user.is_active:
            raise UserBlockedError()
        if user.password_changed_at and int(user.password_changed_at.timestamp()) > claims.iat:
            raise TokenRevokedError()

        token_pair = self.jwt_service.issue_token_pair(user.id, user.role)

        await self.refresh_blacklist_repository.create(
            RefreshBlacklistCreateSchema(
                jti=claims.jti,
                expires_at=datetime.fromtimestamp(claims.exp, UTC),
            )
        )
        await self.refresh_token_repository.delete_by_jti(claims.jti)
        await self.refresh_token_repository.create(
            RefreshTokenCreateSchema(
                jti=token_pair.refresh.claims.jti,
                user_id=user.id,
                issued_at=datetime.fromtimestamp(token_pair.refresh.claims.iat, UTC),
                expires_at=datetime.fromtimestamp(token_pair.refresh.claims.exp, UTC),
            )
        )

        return RefreshTokensResponseSchema(
            access_token=token_pair.access.value,
            refresh_token=token_pair.refresh.value,
            expires_in=self.settings.access_token_ttl_seconds,
        )

    def _decode_refresh_token(self, token: str):
        try:
            return self.jwt_service.decode(token)
        except JwtExpiredError as exc:
            raise TokenExpiredError() from exc
        except JwtInvalidError as exc:
            raise InvalidTokenError() from exc
