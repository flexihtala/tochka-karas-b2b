"""Use-case для входящего канала POST /api/v1/b2b/events.

ADR (M3): обработка событий B2B напрямую дергает TicketRepository — без отдельного
TicketService. На M3 поведение тривиально (PENDING/ARCHIVED), полноценный
TicketService с FSM-логикой появится в M4/M5, когда добавятся claim/release/decision.

Логика согласно спеке + moderation-flows.md (упрощённая M3-версия — без HARD_BLOCKED,
без вызовов B2B GET /products/{id}, без queue_priority вычисления):
- CREATED:  создать новый ticket(status=PENDING).
- EDITED:   найти активный ticket по product_id → status=PENDING (сброс claim).
            Если активного нет → 404.
- DELETED:  ARCHIVE все НЕ ARCHIVED тикеты товара. Идемпотентно: если ничего нет — ok.
"""

from apps.events.errors import TicketNotFoundForEditError, UnsupportedEventTypeError
from apps.events.schemas.request import B2BEventTypeEnum, IncomingB2BEventSchema
from apps.events.schemas.response import EventAcceptedResponseSchema
from apps.tickets.enums import TicketStatus
from apps.tickets.repositories import TicketRepository
from apps.tickets.schemas.db import TicketCreateSchema, TicketUpdateSchema


class HandleB2BEventUseCase:
    def __init__(self, ticket_repository: TicketRepository):
        self.ticket_repository = ticket_repository

    async def __call__(self, event: IncomingB2BEventSchema) -> EventAcceptedResponseSchema:
        match event.event_type:
            case B2BEventTypeEnum.CREATED:
                return await self._on_created(event)
            case B2BEventTypeEnum.EDITED:
                return await self._on_edited(event)
            case B2BEventTypeEnum.DELETED:
                return await self._on_deleted(event)
            case _:
                # Pydantic уже отфильтрует, но защитим use-case.
                raise UnsupportedEventTypeError(str(event.event_type))

    async def _on_created(self, event: IncomingB2BEventSchema) -> EventAcceptedResponseSchema:
        seller_id = event.payload.seller_id
        if seller_id is None:
            # Согласно спеке EventProductCreated.seller_id обязательно — но в B2BEventPayloadSchema
            # делаем optional, поэтому проверяем явно.
            raise UnsupportedEventTypeError('CREATED без seller_id')
        ticket = await self.ticket_repository.create(
            TicketCreateSchema(
                product_id=event.payload.product_id,
                seller_id=seller_id,
                status=TicketStatus.PENDING.value,
            )
        )
        return EventAcceptedResponseSchema(ticket_id=ticket.id)

    async def _on_edited(self, event: IncomingB2BEventSchema) -> EventAcceptedResponseSchema:
        existing = await self.ticket_repository.get_active_for_product(event.payload.product_id)
        if existing is None:
            raise TicketNotFoundForEditError()
        updated = await self.ticket_repository.update(
            TicketUpdateSchema(
                id=existing.id,
                status=TicketStatus.PENDING.value,
                claimed_by=None,
                claimed_at=None,
            )
        )
        ticket_id = updated.id if updated is not None else existing.id
        return EventAcceptedResponseSchema(ticket_id=ticket_id)

    async def _on_deleted(self, event: IncomingB2BEventSchema) -> EventAcceptedResponseSchema:
        await self.ticket_repository.archive_for_product(event.payload.product_id)
        return EventAcceptedResponseSchema()
