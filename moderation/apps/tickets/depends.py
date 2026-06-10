from dishka import Provider, Scope, provide

from apps.tickets.b2b_client import ModerationB2BClient
from apps.tickets.repositories import TicketRepository
from apps.tickets.use_cases import (
    ApproveTicketUseCase,
    BlockTicketUseCase,
    ReleaseTicketUseCase,
)
from settings import ModerationSettings
from shared.http_clients import ServiceClient


class TicketsProvider(Provider):
    ticket_repository = provide(TicketRepository, scope=Scope.REQUEST)

    release_ticket_use_case = provide(ReleaseTicketUseCase, scope=Scope.REQUEST)
    approve_ticket_use_case = provide(ApproveTicketUseCase, scope=Scope.REQUEST)
    block_ticket_use_case = provide(BlockTicketUseCase, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def get_b2b_service_client(self, settings: ModerationSettings) -> ServiceClient:
        """Один ServiceClient на приложение: base_url=b2b_url, key=mod_to_b2b_key."""
        return ServiceClient(base_url=settings.b2b_url, service_key=settings.mod_to_b2b_key)

    @provide(scope=Scope.APP)
    def get_b2b_client(self, service_client: ServiceClient) -> ModerationB2BClient:
        return ModerationB2BClient(service_client=service_client)
