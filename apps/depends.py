from dishka import Provider, Scope, provide

from apps.auth.depends import AuthProvider
from apps.products.depends import ProductsProvider
from apps.skus.depends import SkusProvider
from db import SessionManager
from settings import Settings, settings


class CoreProvider(Provider):
    @provide(scope=Scope.APP)
    def get_settings(self) -> Settings:
        return settings

    @provide(scope=Scope.APP)
    def get_session_manager(self, settings: Settings) -> SessionManager:
        return SessionManager(settings)


providers = [CoreProvider(), AuthProvider(), ProductsProvider(), SkusProvider()]
