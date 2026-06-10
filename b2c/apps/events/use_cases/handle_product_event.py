"""Use case POST /api/v1/b2b/events — обработка событий от B2B.

См. canon: b2c-orders-flows.md, Flow B2C-12 и spec neomarket-protocols/b2c/openapi.yaml.
Поддерживает per spec:
- PRODUCT_BLOCKED / PRODUCT_HARD_BLOCKED → пометить SKU/product недоступным.
- PRODUCT_DELETED → пометить product удалённым.
- SKU_OUT_OF_STOCK → пометить SKU нет в наличии.
- SKU_BACK_IN_STOCK / PRICE_CHANGED → idempotent ACK без локальных изменений
  (триггер уведомлений вне scope этого PR).

Поведение (см. ADR US-ORD-04):

1. Идемпотентность через shared.inbox.IdempotentHandler — UNIQUE(sender, key)
   на таблице processed_events; первый INSERT успешен, повторы возвращают
   cached payload без побочных эффектов.

2. Записываем sku_ids в sku_unavailability (reason = event-type). Это локальный
   кэш недоступности — НЕ источник истины (источник — B2B GET /skus при
   следующем GET /cart). Cart-items в БД не модифицируются.

3. Orders НЕ затрагиваются — цены в orders зафиксированы при checkout (см. canon).
"""

from typing import Any

from apps.events.repositories import SkuUnavailabilityRepository
from apps.events.schemas import (
    ProductEventRequestSchema,
    ProductEventResponseSchema,
    ProductEventType,
)
from apps.inbox.models import ProcessedEvent
from shared.db import SessionManager
from shared.inbox import IdempotentHandler
from shared.types import ServiceName

# Маппинг event-type → reason — храним совпадающие строки с UnavailableReason.
# Per spec b2c openapi.yaml: PRODUCT_HARD_BLOCKED → тот же reason 'BLOCKED'
# (на уровне B2C обращение одинаковое — продукт скрыт).
_REASON_BY_EVENT: dict[ProductEventType, str | None] = {
    ProductEventType.PRODUCT_BLOCKED: 'BLOCKED',
    ProductEventType.PRODUCT_HARD_BLOCKED: 'BLOCKED',
    ProductEventType.PRODUCT_DELETED: 'DELETED',
    ProductEventType.SKU_OUT_OF_STOCK: 'OUT_OF_STOCK',
    # spec-types без локального побочного эффекта — принимаем idempotent.
    ProductEventType.SKU_BACK_IN_STOCK: None,
    ProductEventType.PRICE_CHANGED: None,
}


class HandleProductEventUseCase:
    """Обрабатывает POST /api/v1/b2b/events идемпотентно."""

    def __init__(
        self,
        session_manager: SessionManager,
        idempotent_handler: IdempotentHandler[ProcessedEvent],
        unavailability_repository: SkuUnavailabilityRepository,
    ):
        self.session_manager = session_manager
        self.idempotent_handler = idempotent_handler
        self.unavailability_repository = unavailability_repository

    async def __call__(self, payload: ProductEventRequestSchema) -> ProductEventResponseSchema:
        async with self.session_manager.get_session() as session:
            cached_or_result = await self.idempotent_handler.handle(
                session=session,
                sender=ServiceName.B2B,
                key=payload.idempotency_key,
                handler=lambda: self._apply(session, payload),
                result_to_payload=self._serialize_payload,
            )
        return self._coerce_response(cached_or_result)

    async def _apply(
        self,
        session: Any,
        payload: ProductEventRequestSchema,
    ) -> ProductEventResponseSchema:
        """Реальная обработка (вызывается только при первом успешном INSERT в inbox).

        Записывает SKU в sku_unavailability. Cart-items НЕ модифицируются
        (см. ADR — реакция отражается на следующем GET /cart, обогащение из B2B).
        """
        reason = _REASON_BY_EVENT.get(payload.event)
        if reason is not None:
            await self.unavailability_repository.upsert_many(
                session,
                sku_ids=payload.sku_ids,
                reason=reason,
                product_id=payload.product_id,
                event_idempotency_key=payload.idempotency_key,
            )
        return ProductEventResponseSchema(accepted=True)

    @staticmethod
    def _serialize_payload(result: ProductEventResponseSchema) -> dict[str, Any]:
        return result.model_dump(mode='json')

    @staticmethod
    def _coerce_response(value: Any) -> ProductEventResponseSchema:
        """IdempotentHandler возвращает либо ResultT, либо cached dict из БД."""
        if isinstance(value, ProductEventResponseSchema):
            return value
        if isinstance(value, dict):
            return ProductEventResponseSchema.model_validate(value)
        return ProductEventResponseSchema(accepted=True)


__all__ = ['HandleProductEventUseCase']
