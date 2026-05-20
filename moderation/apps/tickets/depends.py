from dishka import Provider, Scope, provide

from apps.tickets.repositories import TicketRepository
from apps.tickets.use_cases import (
    ApproveTicketUseCase,
    BlockTicketUseCase,
    ReleaseTicketUseCase,
)


class TicketsProvider(Provider):
    ticket_repository = provide(TicketRepository, scope=Scope.REQUEST)

    release_ticket_use_case = provide(ReleaseTicketUseCase, scope=Scope.REQUEST)
    approve_ticket_use_case = provide(ApproveTicketUseCase, scope=Scope.REQUEST)
    block_ticket_use_case = provide(BlockTicketUseCase, scope=Scope.REQUEST)
