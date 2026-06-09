from dishka import Provider, Scope, provide

from apps.auth.repositories import RefreshBlacklistRepository, RefreshTokenRepository, UserRepository
from apps.auth.use_cases import LoginUseCase, LogoutUseCase, RefreshUseCase, RegisterBuyerUseCase
from settings import B2CSettings
from shared.auth_lib import JwtService, PasswordHasher


class AuthProvider(Provider):
    @provide(scope=Scope.APP)
    def get_password_hasher(self) -> PasswordHasher:
        return PasswordHasher()

    @provide(scope=Scope.APP)
    def get_jwt_service(self, settings: B2CSettings) -> JwtService:
        return JwtService(settings)

    user_repository = provide(UserRepository, scope=Scope.REQUEST)
    refresh_token_repository = provide(RefreshTokenRepository, scope=Scope.REQUEST)
    refresh_blacklist_repository = provide(RefreshBlacklistRepository, scope=Scope.REQUEST)

    register_buyer_use_case = provide(RegisterBuyerUseCase, scope=Scope.REQUEST)
    login_use_case = provide(LoginUseCase, scope=Scope.REQUEST)
    refresh_use_case = provide(RefreshUseCase, scope=Scope.REQUEST)
    logout_use_case = provide(LogoutUseCase, scope=Scope.REQUEST)
