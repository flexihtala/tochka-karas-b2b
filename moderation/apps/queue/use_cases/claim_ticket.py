from uuid import UUID

from apps.queue.errors import QueueEmptyError
from apps.tickets.repositories import TicketRepository
from apps.tickets.schemas.response import TicketResponseSchema


class ClaimTicketUseCase:
    """POST /api/v1/queue/claim — взять следующий PENDING-тикет.

    Use-case делегирует SQL-уровень `claim_next()` репозиторию, который под капотом
    использует `SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`. Это гарантирует, что
    два одновременных claim'а не получат один тикет — конкурент пропустит
    залоченную строку и возьмёт следующую (или вернёт None, если очередь пуста).
    """

    def __init__(self, ticket_repository: TicketRepository):
        self.ticket_repository = ticket_repository

    async def __call__(self, moderator_id: UUID) -> TicketResponseSchema:
        ticket = await self.ticket_repository.claim_next(moderator_id)
        if ticket is None:
            raise QueueEmptyError()
        return TicketResponseSchema.model_validate(ticket)
