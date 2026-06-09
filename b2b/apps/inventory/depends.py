"""Dishka provider + FastAPI service-key dependency для inventory."""

from dishka import Provider, Scope, provide
from fastapi import Header

from apps.inbox.repositories import InboxRepository
from apps.inventory.repositories import FulfilledOrderRepository, InventoryRepository
from apps.inventory.use_cases import (
    FulfillInventoryUseCase,
    ReserveInventoryUseCase,
    UnreserveInventoryUseCase,
)
from settings import settings
from shared.errors.base import UnauthorizedError
from shared.types import ServiceKeyDirection


def verify_b2c_to_b2b_service_key(
    x_service_key: str | None = Header(default=None, alias='X-Service-Key'),
) -> None:
    """FastAPI dependency: проверяет, что X-Service-Key совпадает с b2c_to_b2b_key.

    Реализована напрямую (без shared.inbox.make_verify_service_key) — фабрика
    из shared полагается на closure, что неудобно для тестов FastAPI
    DI-override. Здесь читаем `settings.b2c_to_b2b_key` ленивее (через
    функцию `_expected_key`), чтобы pytest мог переопределить env-переменную
    до загрузки use-case'а.
    """
    expected = _expected_key()
    if not x_service_key or x_service_key != expected:
        raise UnauthorizedError(
            message=f'Invalid or missing X-Service-Key for direction {ServiceKeyDirection.B2C_TO_B2B.value}',
            code='INVALID_SERVICE_KEY',
        )


def _expected_key() -> str:
    return settings.b2c_to_b2b_key


class InventoryProvider(Provider):
    inventory_repository = provide(InventoryRepository, scope=Scope.REQUEST)
    inbox_repository = provide(InboxRepository, scope=Scope.REQUEST)
    fulfilled_order_repository = provide(FulfilledOrderRepository, scope=Scope.REQUEST)

    reserve_use_case = provide(ReserveInventoryUseCase, scope=Scope.REQUEST)
    unreserve_use_case = provide(UnreserveInventoryUseCase, scope=Scope.REQUEST)
    fulfill_use_case = provide(FulfillInventoryUseCase, scope=Scope.REQUEST)
