from dishka import Provider, Scope, provide

from apps.queue.use_cases import (
    ClaimTicketUseCase,
    ListQueueUseCase,
)


class QueueProvider(Provider):
    list_queue_use_case = provide(ListQueueUseCase, scope=Scope.REQUEST)
    claim_ticket_use_case = provide(ClaimTicketUseCase, scope=Scope.REQUEST)
