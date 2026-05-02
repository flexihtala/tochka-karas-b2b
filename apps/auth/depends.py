from dishka import Provider, Scope, provide

from apps.auth.repositories import RefreshBlacklistRepository, RefreshTokenRepository, UserRepository
from apps.auth.services.jwt_service import JwtService
from apps.auth.services.password_hasher import PasswordHasher
from apps.auth.use_cases import LoginUseCase, LogoutUseCase, RefreshUseCase, RegisterSellerUseCase
from settings import Settings


class AuthProvider(Provider):
    @provide(scope=Scope.APP)
    def get_password_hasher(self) -> PasswordHasher:
        return PasswordHasher()

    @provide(scope=Scope.APP)
    def get_jwt_service(self, settings: Settings) -> JwtService:
        return JwtService(settings)

    user_repository = provide(UserRepository, scope=Scope.REQUEST)
    refresh_token_repository = provide(RefreshTokenRepository, scope=Scope.REQUEST)
    refresh_blacklist_repository = provide(RefreshBlacklistRepository, scope=Scope.REQUEST)

    register_seller_use_case = provide(RegisterSellerUseCase, scope=Scope.REQUEST)
    login_use_case = provide(LoginUseCase, scope=Scope.REQUEST)
    refresh_use_case = provide(RefreshUseCase, scope=Scope.REQUEST)
    logout_use_case = provide(LogoutUseCase, scope=Scope.REQUEST)
