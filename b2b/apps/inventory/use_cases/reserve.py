"""US-B2B-08: реализация POST /api/v1/inventory/reserve.

Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#reserve-sku):

- **All-or-nothing**: блокируем все строки SKU `SELECT ... FOR UPDATE` в одной
  транзакции. Если хотя бы у одного SKU `active_quantity < quantity` →
  поднимаем InventoryConflictError (409 RESERVE_FAILED), вся транзакция
  откатывается (другие SKU не списываются).
- При успехе: `active_quantity -= quantity`, `reserved_quantity += quantity`.
- Идемпотентность: по `(sender=b2c, idempotency_key)` через таблицу
  `processed_events` (InboxRepository). Повтор → возвращаем cached response.
- Если после успешного резерва у SKU `active_quantity = 0` — кладём событие
  `SKU_OUT_OF_STOCK` в outbox с target=b2c (один outbox-row на каждый
  обнулённый SKU).
- Аутентификация: X-Service-Key (направление b2c_to_b2b). Проверяется
  на уровне роутера через FastAPI dependency.

Транзакционная граница use-case:
    [SELECT processed_events] →
    [SELECT skus FOR UPDATE + validate + UPDATE skus] →
    [INSERT outbox для каждого reached_zero SKU] →
    [INSERT processed_events (cached_response)] →
    COMMIT
Всё в одной session-транзакции для атомарной idempotency.
"""

from apps.inbox.repositories import InboxRepository
from apps.inventory.enums import InventoryEventType
from apps.inventory.repositories import InventoryRepository
from apps.inventory.schemas import (
    ReserveItemResponseSchema,
    ReserveRequestSchema,
    ReserveResponseSchema,
)
from apps.outbox.repositories import B2BOutboxRepository
from db import SessionManager
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName


class ReserveInventoryUseCase:
    def __init__(
        self,
        inventory_repository: InventoryRepository,
        outbox_repository: B2BOutboxRepository,
        inbox_repository: InboxRepository,
        session_manager: SessionManager,
    ):
        self.inventory_repository = inventory_repository
        self.outbox_repository = outbox_repository
        self.inbox_repository = inbox_repository
        self.session_manager = session_manager

    async def __call__(self, data: ReserveRequestSchema) -> ReserveResponseSchema:
        sender = ServiceName.B2C

        async with self.session_manager.get_session() as session:
            # 1. Идемпотентность: уже обрабатывали этот ключ?
            cached = await self.inbox_repository.get_cached_response(session, sender, data.idempotency_key)
            if cached is not None:
                return ReserveResponseSchema.model_validate(cached)

            # 2. Reserve: SELECT FOR UPDATE + validate + UPDATE (атомарно)
            items = [(it.sku_id, it.quantity) for it in data.items]
            reserve_results = await self.inventory_repository.reserve(session, items)

            # 3. Для каждого SKU, у которого active_quantity стал 0 — outbox SKU_OUT_OF_STOCK → b2c
            for r in reserve_results:
                if r.reached_zero:
                    await self.outbox_repository.enqueue(
                        session,
                        OutboxEnqueueSchema(
                            event_type=InventoryEventType.SKU_OUT_OF_STOCK.value,
                            target_service=ServiceName.B2C,
                            payload={'sku_id': str(r.sku_id)},
                        ),
                    )

            # 4. Сформировать ответ
            response = ReserveResponseSchema(
                reserved=True,
                items=[
                    ReserveItemResponseSchema(
                        sku_id=r.sku_id,
                        reserved_quantity=r.reserved_quantity,
                        remaining_stock=r.remaining_stock,
                    )
                    for r in reserve_results
                ],
            )

            # 5. Записать idempotency-кеш
            await self.inbox_repository.record(
                session,
                sender,
                data.idempotency_key,
                response.model_dump(mode='json'),
            )
            return response
