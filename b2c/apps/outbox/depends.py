from dishka import Provider, Scope, provide

from apps.outbox.repositories import B2COutboxRepository


class OutboxProvider(Provider):
    outbox_repository = provide(B2COutboxRepository, scope=Scope.REQUEST)
