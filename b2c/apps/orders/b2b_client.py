"""B2BInventoryClient — обёртка над shared.http_clients.ServiceClient для
inventory/catalog-эндпоинтов B2B.

Реализует контракт b2c-orders-flows.md + b2c openapi.yaml:
- POST /api/v1/public/products/batch — снапшот цен/наличия (JSON-массив товаров)
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

    async def get_products_batch(self, product_ids: list[UUID]) -> dict[UUID, dict[str, Any]]:
        """Batch `POST /api/v1/public/products/batch` — снапшот product_title/sku_name/price.

        Тело: {"product_ids": [...]}. Ответ — JSON-**массив** видимых товаров
        (а не dict): [{id, title, status, skus: [{id, product_id, name, price,
        discount, stock_quantity, active_quantity, article, images}], ...}].
        Невидимые/удалённые товары просто отсутствуют в выдаче.

        Возвращает плоский индекс по SKU:
            {sku_id: {product_id, product_title, sku_name, price, active_quantity}}
        — checkout сам решит, как реагировать на отсутствующие SKU.
        """
        if not product_ids:
            return {}
        try:
            payload = await self.service_client.post(
                '/api/v1/public/products/batch',
                json={'product_ids': [str(pid) for pid in product_ids]},
            )
        except ServiceClientError as exc:
            if exc.status_code >= 500:
                raise B2BUnavailableError() from exc
            raise
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise B2BUnavailableError() from exc

        index: dict[UUID, dict[str, Any]] = {}
        for product in payload if isinstance(payload, list) else []:
            if not isinstance(product, dict):
                continue
            product_title = str(product.get('title', ''))
            for sku in product.get('skus') or []:
                if not isinstance(sku, dict):
                    continue
                raw_id = sku.get('id')
                if raw_id is None:
                    continue
                try:
                    sku_id = UUID(str(raw_id))
                except ValueError:
                    continue
                raw_product_id = sku.get('product_id') or product.get('id')
                if raw_product_id is None:
                    continue
                try:
                    product_id = UUID(str(raw_product_id))
                except ValueError:
                    continue
                index[sku_id] = {
                    'product_id': product_id,
                    'product_title': product_title,
                    'sku_name': str(sku.get('name', '')),
                    'price': int(sku.get('price', 0)),
                    'active_quantity': int(sku.get('active_quantity', 0)),
                }
        return index

    async def reserve(
        self,
        *,
        idempotency_key: UUID,
        order_id: UUID,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """POST /api/v1/inventory/reserve.

        B2B ReserveRequestSchema требует [idempotency_key, order_id, items], где
        items = [{sku_id, quantity}]. Дедуп идёт по idempotency_key, поэтому
        per-request order_id безопасен. 200 → {order_id, status, reserved_at};
        409 → ReserveFailedError(details.failed_items); 5xx/timeout → B2BUnavailable.
        """
        payload = {
            'idempotency_key': str(idempotency_key),
            'order_id': str(order_id),
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
