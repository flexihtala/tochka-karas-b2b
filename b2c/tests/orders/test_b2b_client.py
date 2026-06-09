"""Тесты B2BInventoryClient через реальный ServiceClient + httpx.MockTransport.

Мокаем ТОЛЬКО HTTP-границу: ServiceClient(transport=MockTransport) исполняет весь
прод-код (заголовки X-Service-Key, разбор JSON, ServiceClientError), а MockTransport
интерсептит исходящие запросы.
"""

from uuid import uuid4

import httpx
import pytest

from apps.orders.b2b_client import B2BInventoryClient
from apps.orders.errors import B2BUnavailableError, ReserveFailedError
from shared.http_clients import ServiceClient


def _make_client(handler) -> B2BInventoryClient:
    transport = httpx.MockTransport(handler)
    sc = ServiceClient(base_url='http://b2b.test', service_key='k', transport=transport)
    return B2BInventoryClient(service_client=sc)


@pytest.mark.anyio
async def test_get_products_batch_hits_batch_path_with_service_key():
    sku_id = uuid4()
    product_id = uuid4()
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen['path'] = request.url.path
        seen['service_key'] = request.headers.get('X-Service-Key')
        import json as _json

        seen['body'] = _json.loads(request.content)
        return httpx.Response(
            200,
            json=[
                {
                    'id': str(product_id),
                    'title': 'Phone',
                    'status': 'MODERATED',
                    'skus': [
                        {
                            'id': str(sku_id),
                            'product_id': str(product_id),
                            'name': '128GB',
                            'price': 12_999_000,
                            'active_quantity': 7,
                            'article': 'A-1',
                            'images': [],
                        }
                    ],
                }
            ],
        )

    client = _make_client(handler)
    index = await client.get_products_batch([product_id])

    assert seen['path'] == '/api/v1/public/products/batch'
    assert seen['service_key'] == 'k'
    assert seen['body'] == {'product_ids': [str(product_id)]}
    assert sku_id in index
    assert index[sku_id]['price'] == 12_999_000
    assert index[sku_id]['active_quantity'] == 7
    assert index[sku_id]['product_title'] == 'Phone'
    assert index[sku_id]['sku_name'] == '128GB'
    assert index[sku_id]['product_id'] == product_id


@pytest.mark.anyio
async def test_get_products_batch_omits_missing_products():
    """Невидимые товары просто отсутствуют в массиве → не попадают в индекс."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = _make_client(handler)
    index = await client.get_products_batch([uuid4()])
    assert index == {}


@pytest.mark.anyio
async def test_get_products_batch_5xx_raises_b2b_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={'code': 'UNAVAILABLE'})

    client = _make_client(handler)
    with pytest.raises(B2BUnavailableError):
        await client.get_products_batch([uuid4()])


@pytest.mark.anyio
async def test_reserve_hits_reserve_path_with_order_id_and_service_key():
    order_id = uuid4()
    key = uuid4()
    sku_id = uuid4()
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        seen['path'] = request.url.path
        seen['service_key'] = request.headers.get('X-Service-Key')
        seen['body'] = _json.loads(request.content)
        return httpx.Response(200, json={'order_id': str(order_id), 'status': 'RESERVED', 'reserved_at': 'now'})

    client = _make_client(handler)
    res = await client.reserve(
        idempotency_key=key,
        order_id=order_id,
        items=[{'sku_id': str(sku_id), 'quantity': 2}],
    )

    assert seen['path'] == '/api/v1/inventory/reserve'
    assert seen['service_key'] == 'k'
    # order_id MUST be in the reserve payload (bug #2 fix).
    assert seen['body']['order_id'] == str(order_id)
    assert seen['body']['idempotency_key'] == str(key)
    assert seen['body']['items'] == [{'sku_id': str(sku_id), 'quantity': 2}]
    assert res['status'] == 'RESERVED'


@pytest.mark.anyio
async def test_reserve_409_with_failed_items_raises_reserve_failed_error():
    sku_id = str(uuid4())
    failed_items = [{'sku_id': sku_id, 'requested': 5, 'available': 1, 'reason': 'INSUFFICIENT_STOCK'}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={'code': 'RESERVE_FAILED', 'message': 'fail', 'details': {'failed_items': failed_items}},
        )

    client = _make_client(handler)
    with pytest.raises(ReserveFailedError) as err:
        await client.reserve(idempotency_key=uuid4(), order_id=uuid4(), items=[])
    assert err.value.failed_items == failed_items


@pytest.mark.anyio
async def test_reserve_409_failed_items_top_level_fallback():
    """Если B2B вернул failed_items на верхнем уровне (без details) — тоже читаем."""
    failed_items = [{'sku_id': str(uuid4()), 'requested': 2, 'available': 0, 'reason': 'OUT_OF_STOCK'}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={'code': 'RESERVE_FAILED', 'failed_items': failed_items})

    client = _make_client(handler)
    with pytest.raises(ReserveFailedError) as err:
        await client.reserve(idempotency_key=uuid4(), order_id=uuid4(), items=[])
    assert err.value.failed_items == failed_items


@pytest.mark.anyio
async def test_reserve_5xx_raises_b2b_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={'code': 'UNAVAILABLE'})

    client = _make_client(handler)
    with pytest.raises(B2BUnavailableError):
        await client.reserve(idempotency_key=uuid4(), order_id=uuid4(), items=[])


@pytest.mark.anyio
async def test_reserve_network_error_raises_b2b_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('cannot connect')

    client = _make_client(handler)
    with pytest.raises(B2BUnavailableError):
        await client.reserve(idempotency_key=uuid4(), order_id=uuid4(), items=[])


@pytest.mark.anyio
async def test_unreserve_5xx_raises_b2b_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={'code': 'BAD_GATEWAY'})

    client = _make_client(handler)
    with pytest.raises(B2BUnavailableError):
        await client.unreserve(order_id=uuid4(), items=[])


@pytest.mark.anyio
async def test_unreserve_sends_order_id_and_items():
    """B2B UnreserveRequestSchema requires {order_id, items}; idempotency is by order_id."""
    order_id = uuid4()
    sku_id = uuid4()
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        seen['path'] = request.url.path
        seen['body'] = _json.loads(request.content)
        return httpx.Response(200, json={'unreserved': True})

    client = _make_client(handler)
    res = await client.unreserve(order_id=order_id, items=[{'sku_id': str(sku_id), 'quantity': 2}])

    assert res == {'unreserved': True}
    assert seen['path'] == '/api/v1/inventory/unreserve'
    assert seen['body'] == {'order_id': str(order_id), 'items': [{'sku_id': str(sku_id), 'quantity': 2}]}
    assert 'idempotency_key' not in seen['body']


@pytest.mark.anyio
async def test_fulfill_returns_ok():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'fulfilled': True})

    client = _make_client(handler)
    res = await client.fulfill(order_id=uuid4(), items=[])
    assert res == {'fulfilled': True}
