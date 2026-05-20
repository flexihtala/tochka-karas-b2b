from apps.tickets.enums import TicketStatus
from apps.tickets.repositories import TicketRepository
from apps.tickets.schemas.response import TicketListResponseSchema, TicketResponseSchema


class ListQueueUseCase:
    """GET /api/v1/queue — просмотр очереди тикетов с пагинацией.

    M2 принимает фильтр по status (для history-view нужны не только PENDING).
    Сортировка из repository.list_(): queue_priority ASC, created_at ASC.
    """

    def __init__(self, ticket_repository: TicketRepository):
        self.ticket_repository = ticket_repository

    async def __call__(
        self,
        *,
        limit: int,
        offset: int,
        status: TicketStatus | None = None,
    ) -> TicketListResponseSchema:
        items, total_count = await self.ticket_repository.list_(
            limit=limit,
            offset=offset,
            status=status,
        )
        return TicketListResponseSchema(
            items=[TicketResponseSchema.model_validate(t) for t in items],
            total_count=total_count,
            limit=limit,
            offset=offset,
        )
