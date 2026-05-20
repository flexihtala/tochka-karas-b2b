from dishka import Provider, Scope, provide

from apps.inbox.models import ProcessedEvent
from apps.inbox.repositories import InboxRepository
from shared.inbox import IdempotentHandler


class InboxProvider(Provider):
    @provide(scope=Scope.APP)
    def get_idempotent_handler(self) -> IdempotentHandler[ProcessedEvent]:
        return IdempotentHandler(ProcessedEvent)

    inbox_repository = provide(InboxRepository, scope=Scope.REQUEST)
