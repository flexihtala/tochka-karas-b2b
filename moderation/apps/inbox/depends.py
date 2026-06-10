from dishka import Provider, Scope, provide

from apps.inbox.repositories import InboxRepository


class InboxProvider(Provider):
    """DI журнала processed_events (идемпотентность входящего канала b2b/events)."""

    inbox_repository = provide(InboxRepository, scope=Scope.REQUEST)
