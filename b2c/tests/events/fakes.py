"""Fakes для unit-тестов apps.events.

Не используем реальную DB / asyncpg — заменяем SessionManager, IdempotentHandler,
SkuUnavailabilityRepository in-memory эквивалентами.
"""

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from shared.types import ServiceName


class FakeSession:
    """Маркер-объект, который передаётся вместо AsyncSession в фейк-реализациях."""

    def __init__(self):
        self.flushed: list[Any] = []

    async def flush(self) -> None:
        return None


class FakeSessionManager:
    """Имитация SessionManager — возвращает FakeSession через context-manager."""

    def __init__(self):
        self.session = FakeSession()
        self.session_calls = 0

    @asynccontextmanager
    async def get_session(self):
        self.session_calls += 1
        yield self.session


class FakeSkuUnavailabilityRepository:
    """Запоминает все upsert_many-вызовы; list_by_skus читает локальный словарь."""

    def __init__(self):
        # sku_id -> {'reason', 'product_id', 'event_idempotency_key'}
        self.records: dict[UUID, dict[str, Any]] = {}
        self.upsert_calls: list[dict[str, Any]] = []

    async def upsert_many(
        self,
        session: Any,
        *,
        sku_ids: list[UUID],
        reason: str,
        product_id: UUID,
        event_idempotency_key: UUID,
    ) -> None:
        self.upsert_calls.append(
            {
                'sku_ids': list(sku_ids),
                'reason': reason,
                'product_id': product_id,
                'event_idempotency_key': event_idempotency_key,
            }
        )
        for sku_id in sku_ids:
            self.records[sku_id] = {
                'reason': reason,
                'product_id': product_id,
                'event_idempotency_key': event_idempotency_key,
            }


class FakeIdempotentHandler:
    """Простейшая идемпотентность по (sender, key) — без БД.

    Соответствует контракту shared.inbox.IdempotentHandler.handle.
    """

    def __init__(self):
        self.processed: dict[tuple[str, UUID], dict[str, Any]] = {}
        self.handler_calls = 0
        self.lookup_calls = 0

    async def handle(
        self,
        *,
        session: Any,
        sender: ServiceName,
        key: UUID,
        handler: Callable[[], Awaitable[Any]],
        result_to_payload: Callable[[Any], dict[str, Any]] | None = None,
    ) -> Any:
        self.lookup_calls += 1
        composite = (sender.value, key)
        if composite in self.processed:
            return self.processed[composite] or {}

        result = await handler()
        self.handler_calls += 1
        cached = result_to_payload(result) if result_to_payload else None
        self.processed[composite] = cached or {}
        return result
