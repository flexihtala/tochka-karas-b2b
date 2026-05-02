from datetime import UTC, datetime

from apps.auth.errors import InvalidTokenError, TokenExpiredError
from apps.auth.repositories import RefreshBlacklistRepository
from apps.auth.schemas.refresh_blacklist import RefreshBlacklistCreateSchema
from apps.auth.schemas.request import LogoutRequestSchema
from apps.auth.schemas.token import AuthenticatedUserSchema
from apps.auth.services.jwt_service import JwtExpiredError, JwtInvalidError, JwtService


class LogoutUseCase:
    def __init__(
        self,
        refresh_blacklist_repository: RefreshBlacklistRepository,
        jwt_service: JwtService,
    ):
        self.refresh_blacklist_repository = refresh_blacklist_repository
        self.jwt_service = jwt_service

    async def __call__(self, data: LogoutRequestSchema, current_user: AuthenticatedUserSchema) -> None:
        refresh_claims = self._decode_refresh_token(data.refresh_token)

        if refresh_claims.sub != current_user.id:
            raise InvalidTokenError()

        if not await self.refresh_blacklist_repository.exists(refresh_claims.jti):
            await self.refresh_blacklist_repository.create(
                RefreshBlacklistCreateSchema(
                    jti=refresh_claims.jti,
                    expires_at=datetime.fromtimestamp(refresh_claims.exp, UTC),
                )
            )

    def _decode_refresh_token(self, token: str):
        return self._decode_token(token)

    def _decode_token(self, token: str):
        try:
            return self.jwt_service.decode(token)
        except JwtExpiredError as exc:
            raise TokenExpiredError() from exc
        except JwtInvalidError as exc:
            raise InvalidTokenError() from exc
