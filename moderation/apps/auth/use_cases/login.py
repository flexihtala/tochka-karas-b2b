from datetime import UTC, datetime

from apps.auth.errors import InvalidCredentialsError, UserBlockedError
from apps.auth.repositories import ModeratorRepository, RefreshTokenRepository
from apps.auth.schemas.refresh_token import RefreshTokenCreateSchema
from apps.auth.schemas.request import LoginRequestSchema
from apps.auth.schemas.response import AuthTokensResponseSchema
from settings import ModerationSettings
from shared.auth_lib import JwtService, PasswordHasher


class LoginUseCase:
    def __init__(
        self,
        moderator_repository: ModeratorRepository,
        refresh_token_repository: RefreshTokenRepository,
        password_hasher: PasswordHasher,
        jwt_service: JwtService,
        settings: ModerationSettings,
    ):
        self.moderator_repository = moderator_repository
        self.refresh_token_repository = refresh_token_repository
        self.password_hasher = password_hasher
        self.jwt_service = jwt_service
        self.settings = settings

    async def __call__(self, data: LoginRequestSchema) -> AuthTokensResponseSchema:
        moderator = await self.moderator_repository.get_by_email(data.email)
        if moderator is None or not self.password_hasher.verify(data.password, moderator.password_hash):
            raise InvalidCredentialsError()
        if not moderator.is_active:
            raise UserBlockedError()

        token_pair = self.jwt_service.issue_token_pair(moderator.id, moderator.role)
        await self.refresh_token_repository.create(
            RefreshTokenCreateSchema(
                jti=token_pair.refresh.claims.jti,
                user_id=moderator.id,
                issued_at=datetime.fromtimestamp(token_pair.refresh.claims.iat, UTC),
                expires_at=datetime.fromtimestamp(token_pair.refresh.claims.exp, UTC),
            )
        )

        return AuthTokensResponseSchema(
            user_id=moderator.id,
            access_token=token_pair.access.value,
            refresh_token=token_pair.refresh.value,
            expires_in=self.settings.access_token_ttl_seconds,
            role=moderator.role,
        )
