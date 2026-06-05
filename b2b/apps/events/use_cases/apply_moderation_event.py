"""US-B2B-09: обработка входящих событий от Moderation-сервиса.

Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#apply-moderation):

- `event_type == MODERATED`:
    1. `product.status -> MODERATED`.
    2. Очистить `blocking_reason_id`, `moderator_comment`, `field_reports`.
- `event_type == BLOCKED, hard_block == False`:
    1. `product.status -> BLOCKED`.
    2. Сохранить `blocking_reason_id`, `moderator_comment`, `field_reports`.
    3. Каскадное событие `PRODUCT_BLOCKED` в outbox (target=b2c) с `sku_ids`.
- `event_type == BLOCKED, hard_block == True`:
    1. `product.status -> HARD_BLOCKED` (терминальный).
    2. Сохранить blocking info.
    3. Каскадное событие `PRODUCT_BLOCKED` в outbox (target=b2c) с `sku_ids`.
- Идемпотентность: (sender_service='moderation', idempotency_key) -- через
  `shared.inbox.IdempotentHandler` (см. apps/inbox/depends.py). Повторный вызов
  с тем же ключом вернёт cached-ответ, без побочных эффектов.

Конкретная транзакционность: `IdempotentHandler.handle` принимает
`AsyncSession`. Запись в `processed_events` происходит в этой же сессии после
выполнения handler. Доменные мутации (`product.update`, `outbox.enqueue`)
в текущей реализации b2b открывают собственные транзакции внутри репозиториев
— это согласуется с тем, как реализованы остальные use-case'ы (см.
US-B2B-02). Полная транзакционность (одна сессия на всё) — отдельный
рефакторинг, выходящий за рамки квеста.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from apps.events.errors import BlockedReasonRequiredError, EventProductNotFoundError
from apps.events.schemas.request import ModerationEventRequestSchema, ModerationEventType
from apps.events.schemas.response import ModerationEventResponseSchema
from apps.inbox.models import ProcessedEvent
from apps.outbox.repositories import B2BOutboxRepository
from apps.products.enums import ProductStatus
from apps.products.repositories import ProductRepository
from apps.products.schemas.db import ProductReadSchema, ProductUpdateSchema
from apps.skus.repositories import SKURepository
from db import SessionManager
from shared.inbox import IdempotentHandler
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName


class ApplyModerationEventUseCase:
    def __init__(
        self,
        session_manager: SessionManager,
        idempotent_handler: IdempotentHandler[ProcessedEvent],
        product_repository: ProductRepository,
        sku_repository: SKURepository,
        outbox_repository: B2BOutboxRepository,
    ):
        self.session_manager = session_manager
        self.idempotent_handler = idempotent_handler
        self.product_repository = product_repository
        self.sku_repository = sku_repository
        self.outbox_repository = outbox_repository

    async def __call__(self, data: ModerationEventRequestSchema) -> ModerationEventResponseSchema:
        async with self.session_manager.get_session() as session:
            result = await self.idempotent_handler.handle(
                session=session,
                sender=ServiceName.MODERATION,
                key=data.idempotency_key,
                handler=lambda: self._execute(data),
                result_to_payload=lambda r: (
                    r.model_dump(mode='json') if isinstance(r, ModerationEventResponseSchema) else r
                ),
            )

        if isinstance(result, ModerationEventResponseSchema):
            return result
        # Cached payload (dict) returned from inbox -- восстанавливаем pydantic-схему.
        return ModerationEventResponseSchema.model_validate(result)

    async def _execute(self, data: ModerationEventRequestSchema) -> ModerationEventResponseSchema:
        product = await self.product_repository.get_or_none(data.product_id)
        if product is None:
            raise EventProductNotFoundError()

        if data.event_type == ModerationEventType.MODERATED:
            return await self._apply_moderated(product)

        # BLOCKED — soft or hard
        if data.blocking_reason_id is None:
            raise BlockedReasonRequiredError()

        new_status = ProductStatus.HARD_BLOCKED if data.hard_block else ProductStatus.BLOCKED
        updated = await self._apply_blocked(
            product=product,
            new_status=new_status,
            blocking_reason_id=data.blocking_reason_id,
            moderator_comment=data.moderator_comment,
            field_reports=data.field_reports,
        )
        await self._enqueue_b2c_cascade(product_id=updated.id)
        return ModerationEventResponseSchema(product_id=updated.id, status=updated.status)

    async def _apply_moderated(self, product: ProductReadSchema) -> ModerationEventResponseSchema:
        updated = await self.product_repository.update(
            ProductUpdateSchema(
                id=product.id,
                status=ProductStatus.MODERATED,
                blocking_reason_id=None,
                moderator_comment=None,
                field_reports=None,
            )
        )
        if updated is None:
            raise EventProductNotFoundError()
        return ModerationEventResponseSchema(product_id=updated.id, status=updated.status)

    async def _apply_blocked(
        self,
        *,
        product: ProductReadSchema,
        new_status: ProductStatus,
        blocking_reason_id,
        moderator_comment: str | None,
        field_reports: list[Any] | None,
    ) -> ProductReadSchema:
        serialized_reports: list[dict[str, Any]] | None
        if field_reports is None:
            serialized_reports = None
        else:
            serialized_reports = [
                {
                    'field_name': fr.field_name,
                    'sku_id': str(fr.sku_id) if fr.sku_id else None,
                    'comment': fr.comment,
                }
                for fr in field_reports
            ]
        updated = await self.product_repository.update(
            ProductUpdateSchema(
                id=product.id,
                status=new_status,
                blocking_reason_id=blocking_reason_id,
                moderator_comment=moderator_comment,
                field_reports=serialized_reports,
            )
        )
        if updated is None:
            raise EventProductNotFoundError()
        return updated

    async def _enqueue_b2c_cascade(self, product_id) -> None:
        sku_ids = await self.sku_repository.list_ids_by_product(product_id)
        payload: dict[str, Any] = {
            'event': 'PRODUCT_BLOCKED',
            'product_id': str(product_id),
            'sku_ids': [str(sid) for sid in sku_ids],
            'date': datetime.now(UTC).isoformat(),
        }
        await self.outbox_repository.enqueue_in_new_transaction(
            OutboxEnqueueSchema(
                idempotency_key=uuid4(),
                event_type='PRODUCT_BLOCKED',
                target_service=ServiceName.B2C,
                payload=payload,
            )
        )
