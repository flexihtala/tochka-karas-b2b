from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.outbox.repositories import ModerationOutboxRepository
from apps.tickets.b2b_client import ModerationB2BClient
from apps.tickets.enums import TicketStatus
from apps.tickets.errors import (
    TicketNoSkusError,
    TicketNotAssignedError,
    TicketNotFoundError,
    TicketWrongStatusError,
)
from apps.tickets.repositories import TicketRepository
from apps.tickets.schemas.db import TicketUpdateSchema
from apps.tickets.schemas.response import TicketResponseSchema
from shared.auth_lib import UserRole
from shared.db import SessionManager
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName


class ApproveTicketUseCase:
    """POST /api/v1/tickets/{id}/approve — одобрить тикет.

    Условия: status == IN_REVIEW, модератор владеет тикетом (или ADMIN), и у товара
    в B2B всё ещё есть хотя бы один SKU. В одной транзакции UPDATE tickets + INSERT
    outbox (event MODERATED для b2b). Доставку в b2b делает OutboxWorker в M3.
    """

    def __init__(
        self,
        ticket_repository: TicketRepository,
        outbox_repository: ModerationOutboxRepository,
        b2b_client: ModerationB2BClient,
        session_manager: SessionManager,
    ):
        self.ticket_repository = ticket_repository
        self.outbox_repository = outbox_repository
        self.b2b_client = b2b_client
        self.session_manager = session_manager

    async def __call__(
        self,
        ticket_id: UUID,
        moderator_id: UUID,
        role: UserRole,
        comment: str | None = None,
    ) -> TicketResponseSchema:
        ticket = await self.ticket_repository.get_or_none(ticket_id)
        if ticket is None:
            raise TicketNotFoundError()

        if ticket.status != TicketStatus.IN_REVIEW:
            raise TicketWrongStatusError()

        if role != UserRole.ADMIN and ticket.claimed_by != moderator_id:
            raise TicketNotAssignedError()

        # Прекондишн: товар в B2B должен всё ещё содержать хотя бы один SKU.
        # B2B — отдельный сервис со своей БД, ходим только по API. На 5xx/timeout
        # клиент поднимет B2BUnavailableError (503) → статус останется IN_REVIEW,
        # модератор повторит approve позже.
        product = await self.b2b_client.get_product(ticket.product_id)
        if product is None or not product.get('skus'):
            raise TicketNoSkusError()

        idempotency_key = uuid4()
        now = datetime.now(UTC)

        async with self.session_manager.get_session() as session:
            update_payload = {
                'id': ticket_id,
                'status': TicketStatus.APPROVED,
                'decision_at': now,
            }
            if comment is not None:
                update_payload['moderator_comment'] = comment
            updated = await self.ticket_repository.update_in_session(
                session,
                TicketUpdateSchema(**update_payload),
            )
            if updated is None:
                raise TicketNotFoundError()

            payload: dict[str, object] = {
                'product_id': str(updated.product_id),
                'idempotency_key': str(idempotency_key),
            }
            if comment is not None:
                payload['comment'] = comment

            await self.outbox_repository.enqueue(
                session,
                OutboxEnqueueSchema(
                    idempotency_key=idempotency_key,
                    event_type='MODERATED',
                    target_service=ServiceName.B2B,
                    payload=payload,
                ),
            )

            return TicketResponseSchema.model_validate(updated)
