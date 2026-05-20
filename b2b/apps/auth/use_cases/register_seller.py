from datetime import UTC, datetime

from apps.auth.enums import UserRole
from apps.auth.errors import EmailAlreadyExistsError, InnAlreadyExistsError
from apps.auth.repositories import RefreshTokenRepository, UserRepository
from apps.auth.schemas.refresh_token import RefreshTokenCreateSchema
from apps.auth.schemas.request import RegisterSellerRequestSchema
from apps.auth.schemas.response import AuthTokensResponseSchema
from apps.auth.schemas.user import UserCreateSchema
from apps.auth.services.jwt_service import JwtService
from apps.auth.services.password_hasher import PasswordHasher
from settings import Settings


class RegisterSellerUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        refresh_token_repository: RefreshTokenRepository,
        password_hasher: PasswordHasher,
        jwt_service: JwtService,
        settings: Settings,
    ):
        self.user_repository = user_repository
        self.refresh_token_repository = refresh_token_repository
        self.password_hasher = password_hasher
        self.jwt_service = jwt_service
        self.settings = settings

    async def __call__(self, data: RegisterSellerRequestSchema) -> AuthTokensResponseSchema:
        if await self.user_repository.get_by_email(data.email):
            raise EmailAlreadyExistsError()
        if await self.user_repository.get_by_inn(data.inn):
            raise InnAlreadyExistsError()

        user = await self.user_repository.create(
            UserCreateSchema(
                email=data.email,
                password_hash=self.password_hasher.hash(data.password),
                role=UserRole.SELLER,
                company_name=data.company_name,
                inn=data.inn,
                first_name=data.first_name,
                last_name=data.last_name,
                phone=data.phone,
            )
        )
        token_pair = self.jwt_service.issue_token_pair(user.id, user.role)
        await self.refresh_token_repository.create(
            RefreshTokenCreateSchema(
                jti=token_pair.refresh.claims.jti,
                user_id=user.id,
                issued_at=datetime.fromtimestamp(token_pair.refresh.claims.iat, UTC),
                expires_at=datetime.fromtimestamp(token_pair.refresh.claims.exp, UTC),
            )
        )

        return AuthTokensResponseSchema(
            user_id=user.id,
            access_token=token_pair.access.value,
            refresh_token=token_pair.refresh.value,
            expires_in=self.settings.access_token_ttl_seconds,
        )
