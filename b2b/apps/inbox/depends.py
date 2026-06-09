"""Dishka provider для inbox-инфраструктуры b2b-сервиса.

`IdempotentHandler` параметризован конкретной b2b-моделью `ProcessedEvent` и
используется use-case'ами, обрабатывающими входящие события от внешних сервисов
(пример: US-B2B-09 — `ApplyModerationEventUseCase`).
"""

from dishka import Provider, Scope, provide

from apps.inbox.models import ProcessedEvent
from shared.inbox import IdempotentHandler


class InboxProvider(Provider):
    @provide(scope=Scope.APP)
    def get_idempotent_handler(self) -> IdempotentHandler[ProcessedEvent]:
        return IdempotentHandler(ProcessedEvent)
