from dishka import Provider, Scope, provide

from apps.outbox.repositories import ModerationOutboxRepository


class OutboxProvider(Provider):
    """Регистрирует репозиторий outbox.

    Use-cases (approve/block) получают его через DI и enqueue'ят события
    в той же транзакции, что и доменный UPDATE.
    """

    outbox_repository = provide(ModerationOutboxRepository, scope=Scope.REQUEST)
