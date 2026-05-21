from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.blocking_reasons.errors import BlockingReasonNotFoundError
from apps.blocking_reasons.repositories import BlockingReasonRepository
from apps.outbox.repositories import ModerationOutboxRepository
from apps.tickets.enums import TicketStatus
from apps.tickets.errors import TicketNotAssignedError, TicketNotFoundError, TicketWrongStatusError
from apps.tickets.repositories import TicketRepository
from apps.tickets.schemas.db import TicketUpdateSchema
from apps.tickets.schemas.request import BlockTicketRequestSchema
from apps.tickets.schemas.response import TicketResponseSchema
from shared.auth_lib import UserRole
from shared.db import SessionManager
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName


class BlockTicketUseCase:
    """POST /api/v1/tickets/{id}/block — заблокировать товар (soft или hard).

    Тело запроса (BlockDecisionRequest по спеке): blocking_reason_ids (array, minItems=1),
    comment (опц.), field_reports (опц.).

    hard_block выводится из выбранных причин: если ХОТЯ БЫ ОДНА причина hard_block=true,
    результирующий статус — HARD_BLOCKED (терминальный, продавец не может исправить).
    Иначе — BLOCKED (продавец может отредактировать и пройти модерацию заново).
    """

    def __init__(
        self,
        ticket_repository: TicketRepository,
        blocking_reason_repository: BlockingReasonRepository,
        outbox_repository: ModerationOutboxRepository,
        session_manager: SessionManager,
    ):
        self.ticket_repository = ticket_repository
        self.blocking_reason_repository = blocking_reason_repository
        self.outbox_repository = outbox_repository
        self.session_manager = session_manager

    async def __call__(
        self,
        ticket_id: UUID,
        data: BlockTicketRequestSchema,
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

        # Резолвим все причины (валидация всех ID, не только первого).
        reasons = []
        for reason_id in data.blocking_reason_ids:
            reason = await self.blocking_reason_repository.get_or_none(reason_id)
            if reason is None or not reason.is_active:
                raise BlockingReasonNotFoundError()
            reasons.append(reason)

        hard_block = any(r.hard_block for r in reasons)
        result_status = TicketStatus.HARD_BLOCKED if hard_block else TicketStatus.BLOCKED
        idempotency_key = uuid4()
        now = datetime.now(UTC)
        # Модель пока хранит одну FK — кладём первую причину; полный список идёт в outbox payload.
        primary_reason_id = data.blocking_reason_ids[0]

        async with self.session_manager.get_session() as session:
            updated = await self.ticket_repository.update_in_session(
                session,
                TicketUpdateSchema(
                    id=ticket_id,
                    status=result_status,
                    decision_at=now,
                    blocking_reason_id=primary_reason_id,
                    moderator_comment=data.comment,
                ),
            )
            if updated is None:
                raise TicketNotFoundError()

            payload: dict[str, object] = {
                'product_id': str(updated.product_id),
                'blocking_reason_ids': [str(rid) for rid in data.blocking_reason_ids],
                'comment': data.comment,
                'hard_block': hard_block,
                'idempotency_key': str(idempotency_key),
            }
            if data.field_reports:
                payload['field_reports'] = [fr.model_dump(mode='json') for fr in data.field_reports]

            await self.outbox_repository.enqueue(
                session,
                OutboxEnqueueSchema(
                    idempotency_key=idempotency_key,
                    event_type='HARD_BLOCKED' if hard_block else 'BLOCKED',
                    target_service=ServiceName.B2B,
                    payload=payload,
                ),
            )

            return TicketResponseSchema.model_validate(updated)
