"""US-B2B-10: реализация POST /api/v1/inventory/fulfill.

Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#fulfill-delivery):

- Списание резерва при доставке: для каждого SKU `reserved_quantity -= quantity`,
  `active_quantity` НЕ меняется (товар уже был исключён из активного остатка
  при reserve).
- Идемпотентность **по `order_id`**: пары `(order_id, sku_id)` запоминаются
  в таблице `fulfilled_orders` (UNIQUE(order_id, sku_id)). Повторный fulfill
  по тому же order_id видит существующие записи и пропускает соответствующие
  items — двойного списания не происходит, ответ всегда {order_id, status='FULFILLED', processed_at}.
- Auth: X-Service-Key (b2c_to_b2b) — на уровне роутера.

Контракт ответа: InventoryOrderResponse из neomarket-protocols/b2b/openapi.yaml.

Отличие от reserve/unreserve: используется НЕ `processed_events`-кеш, а
**отдельная таблица `fulfilled_orders`**. См. ADR-0002 — выбор обоснован
double-deduction risk'ом и тем, что order_id остаётся стабильным даже когда
B2C отправляет разные idempotency_key.

Транзакционная граница use-case:
    [SELECT fulfilled_orders WHERE order_id = ...] →
    [SELECT skus FOR UPDATE + UPDATE skus (только для новых пар)] →
    [INSERT fulfilled_orders для новых пар] →
    COMMIT
Всё в одной session-транзакции — UNIQUE constraint защищает от
параллельных fulfill'ов с одним order_id.
"""

from datetime import UTC, datetime

from apps.inventory.repositories import (
    FulfilledOrderRepository,
    InventoryRepository,
)
from apps.inventory.schemas import FulfillRequestSchema, FulfillResponseSchema
from db import SessionManager


class FulfillInventoryUseCase:
    def __init__(
        self,
        inventory_repository: InventoryRepository,
        fulfilled_order_repository: FulfilledOrderRepository,
        session_manager: SessionManager,
    ):
        self.inventory_repository = inventory_repository
        self.fulfilled_order_repository = fulfilled_order_repository
        self.session_manager = session_manager

    async def __call__(self, data: FulfillRequestSchema) -> FulfillResponseSchema:
        async with self.session_manager.get_session() as session:
            # 1. Узнать, какие (order_id, sku_id) уже записаны — пропустить их
            already_fulfilled = await self.fulfilled_order_repository.get_fulfilled_sku_ids(
                session,
                data.order_id,
            )

            # 2. Отфильтровать items, которые ещё не были fulfilled
            items_to_fulfill = [
                (item.sku_id, item.quantity) for item in data.items if item.sku_id not in already_fulfilled
            ]

            # 3. Если все items уже обработаны — повтор, просто возвращаем FULFILLED.
            if not items_to_fulfill:
                return FulfillResponseSchema(
                    order_id=data.order_id,
                    status='FULFILLED',
                    processed_at=datetime.now(UTC),
                )

            # 4. SELECT FOR UPDATE + UPDATE: reserved_quantity -= quantity (active не меняется)
            await self.inventory_repository.fulfill(session, items_to_fulfill)

            # 5. Зафиксировать факт fulfill'а — UNIQUE(order_id, sku_id) защитит
            #    от двойного списания при гонке параллельных вызовов с одним order_id
            for sku_id, quantity in items_to_fulfill:
                await self.fulfilled_order_repository.record(session, data.order_id, sku_id, quantity)

            return FulfillResponseSchema(
                order_id=data.order_id,
                status='FULFILLED',
                processed_at=datetime.now(UTC),
            )
