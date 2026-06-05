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
