"""B2BInventoryClient — обёртка над shared.http_clients.ServiceClient для
inventory-эндпоинтов B2B.

Реализует контракт b2c-orders-flows.md:
- POST /api/v1/inventory/reserve — 200 OK / 409 RESERVE_FAILED / 5xx
- POST /api/v1/inventory/unreserve — 200 OK / 5xx
- POST /api/v1/inventory/fulfill — 200 OK / 5xx

Маппинг ошибок:
- 409 от reserve → ReserveFailedError (failed_items проксируется как есть)
- 5xx / connection / timeout → B2BUnavailableError (503 наружу)
"""

from typing import Any
from uuid import UUID

import httpx

from apps.orders.errors import B2BUnavailableError, ReserveFailedError
from shared.http_clients import ServiceClient, ServiceClientError


class B2BInventoryClient:
    """Тонкая обёртка над ServiceClient: маршрутизация ошибок в доменные."""

    def __init__(self, service_client: ServiceClient):
        self.service_client = service_client

    async def get_skus_info(self, sku_ids: list[UUID]) -> dict[UUID, dict[str, Any]]:
        """Batch GET /api/v1/skus?ids=... — нужно для снапшота product_title/sku_name/price.

        Возвращает {sku_id: raw_dict}. Отсутствующие SKU (удалённые/невидимые)
        просто не попадут в выдачу — checkout сам решит, как реагировать.

        Ожидаемый контракт от B2B (см. b2c-cart-flows.md): items: [{id, title,
        product_id, product_title, price, available_quantity, blocked}].
        """
        if not sku_ids:
            return {}
        try:
            payload = await self.service_client.get(
                '/api/v1/skus',
                params={'ids': ','.join(str(s) for s in sku_ids)},
            )
        except ServiceClientError as exc:
            if exc.status_code >= 500:
                raise B2BUnavailableError() from exc
            raise
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise B2BUnavailableError() from exc

        index: dict[UUID, dict[str, Any]] = {}
        for raw in payload.get('items', []) if isinstance(payload, dict) else []:
            raw_id = raw.get('id') if isinstance(raw, dict) else None
            if raw_id is None:
                continue
            try:
                sku_id = UUID(str(raw_id))
            except ValueError:
                continue
            index[sku_id] = raw
        return index

    async def reserve(
        self,
        idempotency_key: UUID,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            'idempotency_key': str(idempotency_key),
            'items': items,
        }
        try:
            return await self.service_client.post('/api/v1/inventory/reserve', json=payload)
        except ServiceClientError as exc:
            if exc.status_code == 409 and isinstance(exc.payload, dict):
                failed_items = exc.payload.get('details', {}).get('failed_items')
                if failed_items is None:
                    failed_items = exc.payload.get('failed_items', [])
                raise ReserveFailedError(failed_items=failed_items) from exc
            if exc.status_code >= 500:
                raise B2BUnavailableError() from exc
            raise
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise B2BUnavailableError() from exc

    async def unreserve(
        self,
        idempotency_key: UUID,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            'idempotency_key': str(idempotency_key),
            'items': items,
        }
        try:
            return await self.service_client.post('/api/v1/inventory/unreserve', json=payload)
        except ServiceClientError as exc:
            if exc.status_code >= 500:
                raise B2BUnavailableError() from exc
            raise
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise B2BUnavailableError() from exc

    async def fulfill(self, order_id: UUID, items: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {'order_id': str(order_id), 'items': items}
        try:
            return await self.service_client.post('/api/v1/inventory/fulfill', json=payload)
        except ServiceClientError as exc:
            if exc.status_code >= 500:
                raise B2BUnavailableError() from exc
            raise
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise B2BUnavailableError() from exc
