from dishka import Provider, Scope, provide

from apps.auth.repositories import ModeratorRepository, RefreshBlacklistRepository, RefreshTokenRepository
from apps.auth.use_cases import LoginUseCase, LogoutUseCase, RefreshUseCase
from settings import ModerationSettings
from shared.auth_lib import JwtService, PasswordHasher


class AuthProvider(Provider):
    """Регистрирует репозитории + use cases auth-модуля.

    PasswordHasher и JwtService — singletons (Scope.APP), репозитории и use cases — Scope.REQUEST.
    """

    @provide(scope=Scope.APP)
    def get_password_hasher(self) -> PasswordHasher:
        return PasswordHasher()

    @provide(scope=Scope.APP)
    def get_jwt_service(self, settings: ModerationSettings) -> JwtService:
        return JwtService(settings)

    moderator_repository = provide(ModeratorRepository, scope=Scope.REQUEST)
    refresh_token_repository = provide(RefreshTokenRepository, scope=Scope.REQUEST)
    refresh_blacklist_repository = provide(RefreshBlacklistRepository, scope=Scope.REQUEST)

    login_use_case = provide(LoginUseCase, scope=Scope.REQUEST)
    refresh_use_case = provide(RefreshUseCase, scope=Scope.REQUEST)
    logout_use_case = provide(LogoutUseCase, scope=Scope.REQUEST)
