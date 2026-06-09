from uuid import UUID

from apps.tickets.enums import TicketStatus
from apps.tickets.repositories import TicketRepository
from apps.tickets.schemas.response import TicketListResponseSchema, TicketResponseSchema


class ListQueueUseCase:
    """GET /api/v1/queue — просмотр PENDING-тикетов очереди с пагинацией.

    По спеке возвращаются только PENDING. Сортировка из repository.list_():
    queue_priority ASC, created_at ASC. Доступные фильтры по спеке —
    queue_priority, category_id, seller_id.
    """

    def __init__(self, ticket_repository: TicketRepository):
        self.ticket_repository = ticket_repository

    async def __call__(
        self,
        *,
        limit: int,
        offset: int,
        queue_priority: int | None = None,
        category_id: UUID | None = None,
        seller_id: UUID | None = None,
    ) -> TicketListResponseSchema:
        items, total_count = await self.ticket_repository.list_(
            limit=limit,
            offset=offset,
            status=TicketStatus.PENDING,
            queue_priority=queue_priority,
            category_id=category_id,
            seller_id=seller_id,
        )
        return TicketListResponseSchema(
            items=[TicketResponseSchema.model_validate(t) for t in items],
            total_count=total_count,
            limit=limit,
            offset=offset,
        )
