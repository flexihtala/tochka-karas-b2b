"""Фейки для тестов inventory use-case.

Тесты не покрывают реальное `SELECT ... FOR UPDATE` — это уровень
e2e/интеграции (out of scope). Здесь моделируем ALL-OR-NOTHING семантику
через фейк-репозиторий: при первой непрошедшей проверке raise
`InventoryConflictError` и НЕ применяем мутаций ни к одному SKU.
"""

from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from apps.inventory.enums import ReserveFailureReason
from apps.inventory.errors import InventoryConflictError
from apps.inventory.repositories.inventory_repository import (
    FulfillItemResult,
    ReserveItemResult,
    UnreserveItemResult,
)
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName


class FakeSession:
    """No-op session — нужна, чтобы соблюсти сигнатуру репозиториев."""

    async def execute(self, *args, **kwargs):  # noqa: ANN001
        raise NotImplementedError('FakeSession не используется напрямую в тестах')

    async def flush(self):  # noqa: ANN201
        return None


class FakeSessionManager:
    """Возвращает контекст-менеджер с FakeSession.

    В отличие от реального SessionManager — НЕ открывает БД. Транзакция тоже
    не управляется: транзакционные семантики (rollback) моделируются на
    уровне FakeInventoryRepository (см. ниже).
    """

    @asynccontextmanager
    async def get_session(self):  # noqa: ANN201
        yield FakeSession()


class FakeInventoryRepository:
    """In-memory SKU store с поведением reserve/unreserve.

    Хранит SKU как `{sku_id: {'active_quantity': int, 'reserved_quantity': int}}`.

    Ключевое: при reserve, если хотя бы один SKU не проходит проверку —
    raise InventoryConflictError без применения мутаций. Это и есть
    all-or-nothing на уровне fakes (см. constraint в US-B2B-08).
    """

    def __init__(self) -> None:
        self.skus: dict[UUID, dict[str, int]] = {}
        self.reserve_calls: list[list[tuple[UUID, int]]] = []
        self.unreserve_calls: list[list[tuple[UUID, int]]] = []
        self.fulfill_calls: list[list[tuple[UUID, int]]] = []

    def add_sku(self, sku_id: UUID, *, active: int, reserved: int = 0) -> None:
        self.skus[sku_id] = {'active_quantity': active, 'reserved_quantity': reserved}

    async def reserve(self, session: FakeSession, items: list[tuple[UUID, int]]) -> list[ReserveItemResult]:
        self.reserve_calls.append(list(items))

        sorted_ids = sorted({sku_id for sku_id, _ in items})
        requested_by_id = {sku_id: qty for sku_id, qty in items}

        # Phase 1: validation (без мутаций) — all-or-nothing
        failed_items: list[dict[str, Any]] = []
        for sku_id in sorted_ids:
            requested = requested_by_id[sku_id]
            sku = self.skus.get(sku_id)
            if sku is None:
                failed_items.append(
                    {
                        'sku_id': str(sku_id),
                        'requested': requested,
                        'available': 0,
                        'reason': ReserveFailureReason.NOT_FOUND.value,
                    }
                )
                continue
            if sku['active_quantity'] < requested:
                reason = (
                    ReserveFailureReason.OUT_OF_STOCK
                    if sku['active_quantity'] == 0
                    else ReserveFailureReason.INSUFFICIENT_STOCK
                )
                failed_items.append(
                    {
                        'sku_id': str(sku_id),
                        'requested': requested,
                        'available': sku['active_quantity'],
                        'reason': reason.value,
                    }
                )
        if failed_items:
            # ROLLBACK: ни одна мутация не применяется
            raise InventoryConflictError(failed_items=failed_items)

        # Phase 2: применение
        results: list[ReserveItemResult] = []
        for sku_id in sorted_ids:
            requested = requested_by_id[sku_id]
            sku = self.skus[sku_id]
            sku['active_quantity'] -= requested
            sku['reserved_quantity'] += requested
            results.append(
                ReserveItemResult(
                    sku_id=sku_id,
                    reserved_quantity=requested,
                    remaining_stock=sku['active_quantity'],
                    reached_zero=sku['active_quantity'] == 0,
                )
            )
        return results

    async def unreserve(self, session: FakeSession, items: list[tuple[UUID, int]]) -> list[UnreserveItemResult]:
        self.unreserve_calls.append(list(items))

        sorted_ids = sorted({sku_id for sku_id, _ in items})
        requested_by_id = {sku_id: qty for sku_id, qty in items}

        results: list[UnreserveItemResult] = []
        for sku_id in sorted_ids:
            sku = self.skus.get(sku_id)
            if sku is None:
                continue
            qty = requested_by_id[sku_id]
            sku['reserved_quantity'] -= qty
            sku['active_quantity'] += qty
            results.append(UnreserveItemResult(sku_id=sku_id))
        return results

    async def fulfill(self, session: FakeSession, items: list[tuple[UUID, int]]) -> list[FulfillItemResult]:
        """Списание резерва при доставке: reserved_quantity -= qty, active_quantity НЕ меняется."""
        self.fulfill_calls.append(list(items))

        sorted_ids = sorted({sku_id for sku_id, _ in items})
        requested_by_id = {sku_id: qty for sku_id, qty in items}

        results: list[FulfillItemResult] = []
        for sku_id in sorted_ids:
            sku = self.skus.get(sku_id)
            if sku is None:
                continue
            qty = requested_by_id[sku_id]
            sku['reserved_quantity'] -= qty
            # active_quantity НЕ меняется (см. apps/inventory/repositories/inventory_repository.py:fulfill)
            results.append(FulfillItemResult(sku_id=sku_id))
        return results


class FakeInboxRepository:
    """In-memory кеш processed_events. Ключ — (sender, idempotency_key)."""

    def __init__(self) -> None:
        self.cache: dict[tuple[str, UUID], dict[str, Any]] = {}
        self.records: list[tuple[str, UUID, dict[str, Any]]] = []

    async def get_cached_response(
        self,
        session: FakeSession,
        sender: ServiceName,
        idempotency_key: UUID,
    ) -> dict[str, Any] | None:
        return self.cache.get((sender.value, idempotency_key))

    async def record(
        self,
        session: FakeSession,
        sender: ServiceName,
        idempotency_key: UUID,
        cached_response: dict[str, Any],
    ) -> None:
        key = (sender.value, idempotency_key)
        self.cache[key] = cached_response
        self.records.append((sender.value, idempotency_key, cached_response))


class FakeOutboxRepository:
    """Фейк b2b outbox-репозитория для тестов inventory.

    Тесты проверяют события через `.enqueued` (как и в tests/skus)."""

    def __init__(self) -> None:
        self.enqueued: list[OutboxEnqueueSchema] = []

    async def enqueue(self, session: FakeSession, data: OutboxEnqueueSchema) -> Any:
        self.enqueued.append(data)
        return None

    async def enqueue_in_new_transaction(self, data: OutboxEnqueueSchema) -> Any:
        self.enqueued.append(data)
        return None


class FakeFulfilledOrderRepository:
    """In-memory журнал fulfilled_orders (UNIQUE(order_id, sku_id)).

    Используется в тестах FulfillInventoryUseCase для проверки идемпотентности
    по order_id — повторный fulfill с теми же (order_id, sku_id) не должен
    вызывать `InventoryRepository.fulfill` для уже зафиксированных пар.
    """

    def __init__(self) -> None:
        # Ключ — order_id; значение — словарь sku_id → quantity (последний записанный).
        self.records: dict[UUID, dict[UUID, int]] = {}
        # Лог записей (для assert'ов в тестах: сколько раз вызывался record и с какими аргументами).
        self.record_calls: list[tuple[UUID, UUID, int]] = []

    async def get_fulfilled_sku_ids(self, session: FakeSession, order_id: UUID) -> set[UUID]:
        return set(self.records.get(order_id, {}).keys())

    async def record(self, session: FakeSession, order_id: UUID, sku_id: UUID, quantity: int) -> None:
        self.record_calls.append((order_id, sku_id, quantity))
        self.records.setdefault(order_id, {})[sku_id] = quantity
