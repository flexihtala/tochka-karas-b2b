from dishka import Provider, Scope, provide

from apps.auth.depends import AuthProvider
from apps.moderators.depends import ModeratorsProvider
from settings import ModerationSettings, settings
from shared.db import SessionManager


class CoreProvider(Provider):
    @provide(scope=Scope.APP)
    def get_settings(self) -> ModerationSettings:
        return settings

    @provide(scope=Scope.APP)
    def get_session_manager(self, settings: ModerationSettings) -> SessionManager:
        return SessionManager(settings)


providers = [CoreProvider(), AuthProvider(), ModeratorsProvider()]
