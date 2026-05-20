"""FastAPI-зависимость для проверки X-Service-Key на входящих endpoints."""

from collections.abc import Callable

from fastapi import Header

from shared.errors.base import UnauthorizedError
from shared.types import ServiceKeyDirection


def make_verify_service_key(direction: ServiceKeyDirection, expected_key: str) -> Callable[[str | None], None]:
    """Фабрика-зависимость: проверяет, что X-Service-Key совпадает с ожидаемым.

    Использование:
        verify_b2c_to_b2b = make_verify_service_key(
            ServiceKeyDirection.B2C_TO_B2B, settings.b2c_to_b2b_key
        )

        @router.post('/catalog/products', dependencies=[Depends(verify_b2c_to_b2b)])
        async def list_catalog(...):
            ...
    """

    def _dep(x_service_key: str | None = Header(default=None, alias='X-Service-Key')) -> None:
        if not x_service_key or x_service_key != expected_key:
            raise UnauthorizedError(
                message=f'Invalid or missing X-Service-Key for direction {direction.value}',
                code='INVALID_SERVICE_KEY',
            )

    return _dep
