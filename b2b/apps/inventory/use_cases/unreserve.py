"""US-B2B-08: реализация POST /api/v1/inventory/unreserve (компенсация).

Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#reserve-sku):

- Для каждого item: `reserved_quantity -= quantity`, `active_quantity += quantity`.
- Идемпотентность по `(sender=b2c, idempotency_key)` через таблицу
  `processed_events`. Повтор → возвращаем cached response.
- Auth: X-Service-Key (b2c_to_b2b) — на уровне роутера.

Канон ожидает `{ok: true}` (UnreserveResponseSchema).
"""

from apps.inbox.repositories import InboxRepository
from apps.inventory.repositories import InventoryRepository
from apps.inventory.schemas import UnreserveRequestSchema, UnreserveResponseSchema
from db import SessionManager
from shared.types import ServiceName


class UnreserveInventoryUseCase:
    def __init__(
        self,
        inventory_repository: InventoryRepository,
        inbox_repository: InboxRepository,
        session_manager: SessionManager,
    ):
        self.inventory_repository = inventory_repository
        self.inbox_repository = inbox_repository
        self.session_manager = session_manager

    async def __call__(self, data: UnreserveRequestSchema) -> UnreserveResponseSchema:
        sender = ServiceName.B2C

        async with self.session_manager.get_session() as session:
            cached = await self.inbox_repository.get_cached_response(session, sender, data.idempotency_key)
            if cached is not None:
                return UnreserveResponseSchema.model_validate(cached)

            items = [(it.sku_id, it.quantity) for it in data.items]
            await self.inventory_repository.unreserve(session, items)

            response = UnreserveResponseSchema(ok=True)
            await self.inbox_repository.record(
                session,
                sender,
                data.idempotency_key,
                response.model_dump(mode='json'),
            )
            return response
