"""Тестовые fake-объекты для use-case'ов events.

Содержат минимально необходимый поверхностный API:

- `FakeProductRepositoryForEvents` — get_or_none / update (фейк ProductRepository).
- `FakeSKURepositoryForEvents` — list_ids_by_product.
- `FakeOutboxRepositoryForEvents` — захватывает enqueue-вызовы (см. shared.outbox).
- `FakeIdempotentHandler` — заменяет shared.inbox.IdempotentHandler. На повторный
  вызов с тем же (sender, key) возвращает cached-payload без выполнения handler.
- `FakeSessionManager` — `get_session()` отдаёт фейковую сессию (использовать
  не нужно, т.к. FakeIdempotentHandler не обращается к session).
"""

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from apps.events.schemas.response import ModerationEventResponseSchema
from apps.products.enums import ProductStatus
from apps.products.schemas.db import ProductReadSchema, ProductUpdateSchema
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName


class FakeProductRepositoryForEvents:
    def __init__(self):
        self.by_id: dict[UUID, ProductReadSchema] = {}
        self.updated: list[ProductUpdateSchema] = []

    def add(
        self,
        *,
        id: UUID | None = None,
        seller_id: UUID | None = None,
        category_id: UUID | None = None,
        title: str = 'iPhone 15 Pro Max',
        slug: str = 'iphone-15-pro-max',
        description: str = 'Флагман Apple',
        status: ProductStatus = ProductStatus.ON_MODERATION,
        blocking_reason_id: UUID | None = None,
        moderator_comment: str | None = None,
        field_reports: list[dict[str, Any]] | None = None,
    ) -> UUID:
        product_id = id or uuid4()
        now = datetime.now(UTC)
        product = ProductReadSchema(
            id=product_id,
            seller_id=seller_id or uuid4(),
            category_id=category_id or uuid4(),
            title=title,
            slug=slug,
            description=description,
            status=status,
            deleted=False,
            blocking_reason_id=blocking_reason_id,
            moderator_comment=moderator_comment,
            field_reports=field_reports if field_reports is not None else [],
            created_at=now,
            updated_at=now,
        )
        self.by_id[product_id] = product
        return product_id

    async def get_or_none(self, id_: UUID) -> ProductReadSchema | None:
        return self.by_id.get(id_)

    async def update(self, data: ProductUpdateSchema) -> ProductReadSchema | None:
        self.updated.append(data)
        product = self.by_id.get(data.id)
        if product is None:
            return None
        updates = data.model_dump(exclude_unset=True, exclude={'id'})
        merged = product.model_copy(update=updates)
        self.by_id[data.id] = merged
        return merged


class FakeSKURepositoryForEvents:
    def __init__(self):
        self.ids_by_product: dict[UUID, list[UUID]] = {}

    def add(self, product_id: UUID, sku_ids: list[UUID]) -> None:
        self.ids_by_product[product_id] = list(sku_ids)

    async def list_ids_by_product(self, product_id: UUID) -> list[UUID]:
        return list(self.ids_by_product.get(product_id, []))


class FakeOutboxRepositoryForEvents:
    """Фейк b2b outbox-репозитория. Захватывает enqueue-вызовы для assertions."""

    def __init__(self):
        self.enqueued: list[OutboxEnqueueSchema] = []

    async def enqueue_in_new_transaction(self, data: OutboxEnqueueSchema) -> Any:
        self.enqueued.append(data)
        return None


class FakeIdempotentHandler:
    """Тестовая замена shared.inbox.IdempotentHandler.

    Имитация at-most-once семантики без БД: хранит `(sender, key) -> cached_payload`
    в памяти. Повторный handle() с тем же ключом не вызывает handler, а возвращает
    cached_payload (dict). Совместима по сигнатуре с реальной реализацией.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[ServiceName, UUID]] = []
        self.handler_invocations = 0
        self._cache: dict[tuple[str, UUID], dict[str, Any] | None] = {}

    async def handle(
        self,
        session: Any,
        sender: ServiceName,
        key: UUID,
        handler: Callable[[], Awaitable[Any]],
        result_to_payload: Callable[[Any], dict[str, Any]] | None = None,
    ) -> Any:
        self.calls.append((sender, key))
        cache_key = (sender.value, key)
        if cache_key in self._cache:
            return self._cache[cache_key] or {}

        self.handler_invocations += 1
        result = await handler()
        payload = result_to_payload(result) if result_to_payload else None
        self._cache[cache_key] = payload
        return result


@asynccontextmanager
async def _noop_session() -> Any:
    yield None


class FakeSessionManager:
    """Минимальный фейк db.SessionManager — отдаёт пустую async-сессию."""

    def get_session(self):
        return _noop_session()


def make_moderation_event_response(
    *,
    product_id: UUID,
    status: ProductStatus = ProductStatus.MODERATED,
) -> ModerationEventResponseSchema:
    return ModerationEventResponseSchema(product_id=product_id, status=status)
