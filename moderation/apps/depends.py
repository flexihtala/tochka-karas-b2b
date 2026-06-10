from dishka import Provider, Scope, provide

from apps.auth.depends import AuthProvider
from apps.blocking_reasons.depends import BlockingReasonsProvider
from apps.events.depends import EventsProvider
from apps.inbox.depends import InboxProvider
from apps.moderators.depends import ModeratorsProvider
from apps.outbox.depends import OutboxProvider
from apps.queue.depends import QueueProvider
from apps.tickets.depends import TicketsProvider
from settings import ModerationSettings, settings
from shared.db import SessionManager


class CoreProvider(Provider):
    @provide(scope=Scope.APP)
    def get_settings(self) -> ModerationSettings:
        return settings

    @provide(scope=Scope.APP)
    def get_session_manager(self, settings: ModerationSettings) -> SessionManager:
        return SessionManager(settings)


providers = [
    CoreProvider(),
    AuthProvider(),
    ModeratorsProvider(),
    BlockingReasonsProvider(),
    TicketsProvider(),
    QueueProvider(),
    OutboxProvider(),
    InboxProvider(),
    EventsProvider(),
]
