from uuid import UUID

from apps.tickets.enums import TicketStatus
from apps.tickets.errors import TicketNotAssignedError, TicketNotFoundError, TicketWrongStatusError
from apps.tickets.repositories import TicketRepository
from apps.tickets.schemas.db import TicketUpdateSchema
from apps.tickets.schemas.response import TicketResponseSchema
from shared.auth_lib import UserRole


class ReleaseTicketUseCase:
    """POST /api/v1/tickets/{id}/release — вернуть тикет в очередь.

    Условия:
    - status == IN_REVIEW (иначе 409)
    - тикет назначен текущему модератору или вызывающий — ADMIN (иначе 409)
    """

    def __init__(self, ticket_repository: TicketRepository):
        self.ticket_repository = ticket_repository

    async def __call__(
        self,
        ticket_id: UUID,
        moderator_id: UUID,
        role: UserRole,
    ) -> TicketResponseSchema:
        ticket = await self.ticket_repository.get_or_none(ticket_id)
        if ticket is None:
            raise TicketNotFoundError()

        if ticket.status != TicketStatus.IN_REVIEW:
            raise TicketWrongStatusError()

        if role != UserRole.ADMIN and ticket.claimed_by != moderator_id:
            raise TicketNotAssignedError()

        updated = await self.ticket_repository.update(
            TicketUpdateSchema(
                id=ticket_id,
                status=TicketStatus.PENDING,
                claimed_by=None,
                claimed_at=None,
            ),
        )
        if updated is None:
            raise TicketNotFoundError()
        return TicketResponseSchema.model_validate(updated)
