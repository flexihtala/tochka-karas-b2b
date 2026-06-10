from dishka import Provider, Scope, provide

from apps.outbox.repositories import B2BOutboxRepository


class OutboxProvider(Provider):
    outbox_repository = provide(B2BOutboxRepository, scope=Scope.REQUEST)
