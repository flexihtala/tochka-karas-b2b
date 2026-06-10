"""Use-case для входящего канала POST /api/v1/b2b/events.

ADR: обработка событий B2B напрямую дёргает TicketRepository — без отдельного
TicketService. Поведение тривиально (PENDING/ARCHIVED + терминальная защита).

Идемпотентность (US-MOD-01): idempotency_key фиксируется в processed_events
ПЕРВЫМ шагом, до любых мутаций тикетов. UNIQUE(sender_service, idempotency_key)
— арбитр гонки: повторная/конкурентная доставка ловит IntegrityError →
DuplicateEventError (409 DUPLICATE_EVENT) без побочных эффектов. Это закрывает
и out-of-order ретраи (DELETED раньше CREATED): повтор любого события с тем же
ключом отбрасывается. shared.inbox.IdempotentHandler здесь не подходит — он
переигрывает cached-ответ (202), а спека moderation требует 409 на дубликат.

Логика согласно спеке `neomarket-moderation.yaml` (IncomingB2BEvent.event_type)
и канону moderation-flows.md#hard-block («Необратимость»):
- PRODUCT_CREATED: создать ticket(kind=CREATE, status=PENDING) с json_after из payload.
- PRODUCT_EDITED:  найти активный ticket по product_id.
                   * если он HARD_BLOCKED (терминальный) → IGNORE (no-op, всё ещё 202);
                   * иначе сбросить в PENDING (claimed_by=None, claimed_at=None).
                   Если активного тикета нет → 404.
- PRODUCT_DELETED: архивировать все НЕ ARCHIVED тикеты товара, ВКЛЮЧАЯ HARD_BLOCKED
                   (запись модерации закрыта; в B2B товар остаётся заблокированным).
                   Идемпотентно (повторный delete — no-op).
"""

from uuid import UUID

from sqlalchemy.exc import IntegrityError

from apps.events.errors import DuplicateEventError, TicketNotFoundForEditError, UnsupportedEventTypeError
from apps.events.schemas.request import B2BEventTypeEnum, IncomingB2BEventSchema
from apps.events.schemas.response import EventAcceptedResponseSchema
from apps.inbox.repositories import InboxRepository
from apps.tickets.enums import TicketKind, TicketStatus
from apps.tickets.repositories import TicketRepository
from apps.tickets.schemas.db import TicketCreateSchema, TicketUpdateSchema
from shared.types import ServiceName


class HandleB2BEventUseCase:
    def __init__(self, ticket_repository: TicketRepository, inbox_repository: InboxRepository):
        self.ticket_repository = ticket_repository
        self.inbox_repository = inbox_repository

    async def __call__(self, event: IncomingB2BEventSchema) -> EventAcceptedResponseSchema:
        await self._record_idempotency_key(event.idempotency_key)
        match event.event_type:
            case B2BEventTypeEnum.PRODUCT_CREATED:
                return await self._on_created(event)
            case B2BEventTypeEnum.PRODUCT_EDITED:
                return await self._on_edited(event)
            case B2BEventTypeEnum.PRODUCT_DELETED:
                return await self._on_deleted(event)
            case _:
                # Pydantic уже отфильтрует, но защитим use-case.
                raise UnsupportedEventTypeError(str(event.event_type))

    async def _record_idempotency_key(self, idempotency_key: UUID) -> None:
        """INSERT ключа в processed_events ДО мутаций тикетов.

        IntegrityError по UNIQUE(sender_service, idempotency_key) означает, что
        событие уже обработано (или обрабатывается конкурентно) → 409 без эффектов.
        """
        try:
            await self.inbox_repository.insert(ServiceName.B2B, idempotency_key)
        except IntegrityError as exc:
            raise DuplicateEventError(idempotency_key) from exc

    async def _on_created(self, event: IncomingB2BEventSchema) -> EventAcceptedResponseSchema:
        seller_id = event.payload.seller_id
        if seller_id is None:
            # По спеке EventProductCreated.seller_id обязателен — но в payload-схеме он
            # optional (oneOf), поэтому проверяем явно.
            raise UnsupportedEventTypeError('PRODUCT_CREATED без seller_id')
        ticket = await self.ticket_repository.create(
            TicketCreateSchema(
                product_id=event.payload.product_id,
                seller_id=seller_id,
                category_id=event.payload.category_id,
                kind=TicketKind.CREATE,
                status=TicketStatus.PENDING,
                queue_priority=event.payload.queue_priority or 3,
                json_after=event.payload.json_after,
            )
        )
        return EventAcceptedResponseSchema(ticket_id=ticket.id)

    async def _on_edited(self, event: IncomingB2BEventSchema) -> EventAcceptedResponseSchema:
        existing = await self.ticket_repository.get_active_for_product(event.payload.product_id)
        if existing is None:
            raise TicketNotFoundForEditError()

        # Необратимость: правки товара в терминальном HARD_BLOCKED игнорируются —
        # тикет НЕ сбрасывается в PENDING. Идемпотентно: повтор тоже no-op.
        if existing.status == TicketStatus.HARD_BLOCKED:
            return EventAcceptedResponseSchema(ticket_id=existing.id)

        updated = await self.ticket_repository.update(
            TicketUpdateSchema(
                id=existing.id,
                status=TicketStatus.PENDING,
                claimed_by=None,
                claimed_at=None,
            )
        )
        ticket_id = updated.id if updated is not None else existing.id
        return EventAcceptedResponseSchema(ticket_id=ticket_id)

    async def _on_deleted(self, event: IncomingB2BEventSchema) -> EventAcceptedResponseSchema:
        # Архивирует ВСЕ не-ARCHIVED тикеты, включая HARD_BLOCKED. Идемпотентно.
        await self.ticket_repository.archive_for_product(event.payload.product_id)
        return EventAcceptedResponseSchema()
