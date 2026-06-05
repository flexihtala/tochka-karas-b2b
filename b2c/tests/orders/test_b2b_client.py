"""Тесты B2BInventoryClient через httpx MockTransport."""

from uuid import uuid4

import httpx
import pytest

from apps.orders.b2b_client import B2BInventoryClient
from apps.orders.errors import B2BUnavailableError, ReserveFailedError
from shared.http_clients import ServiceClient


class _PatchedServiceClient(ServiceClient):
    """ServiceClient, который использует MockTransport вместо реального HTTP."""

    def __init__(self, base_url: str, service_key: str, transport: httpx.MockTransport):
        super().__init__(base_url=base_url, service_key=service_key)
        self._transport = transport

    async def _request(self, method, path, **kwargs):  # type: ignore[override]
        # Заменяем AsyncClient на MockTransport-вариант.
        import httpx as _httpx

        url = f'{self.base_url}{path}'
        headers = {'X-Service-Key': self.service_key}
        if kwargs.get('idempotency_key'):
            headers['Idempotency-Key'] = kwargs['idempotency_key']

        async with _httpx.AsyncClient(transport=self._transport) as client:
            response = await client.request(
                method,
                url,
                json=kwargs.get('json'),
                params=kwargs.get('params'),
                headers=headers,
            )

        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            from shared.http_clients import ServiceClientError

            raise ServiceClientError(
                status_code=response.status_code,
                message=f'{method} {path} failed',
                payload=payload,
            )

        if not response.content:
            return {}
        return response.json()


def _make_client(handler):
    transport = httpx.MockTransport(handler)
    sc = _PatchedServiceClient(base_url='http://b2b.test', service_key='k', transport=transport)
    return B2BInventoryClient(service_client=sc)


@pytest.mark.anyio
async def test_reserve_returns_payload_on_200():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers['X-Service-Key'] == 'k'
        return httpx.Response(200, json={'reserved': True, 'items': []})

    client = _make_client(handler)
    res = await client.reserve(idempotency_key=uuid4(), items=[])
    assert res == {'reserved': True, 'items': []}


@pytest.mark.anyio
async def test_reserve_409_with_failed_items_raises_reserve_failed_error():
    sku_id = str(uuid4())
    failed_items = [{'sku_id': sku_id, 'requested': 5, 'available': 1, 'reason': 'INSUFFICIENT_STOCK'}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                'code': 'RESERVE_FAILED',
                'message': 'fail',
                'details': {'failed_items': failed_items},
            },
        )

    client = _make_client(handler)
    with pytest.raises(ReserveFailedError) as err:
        await client.reserve(idempotency_key=uuid4(), items=[])
    assert err.value.failed_items == failed_items


@pytest.mark.anyio
async def test_reserve_5xx_raises_b2b_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={'code': 'UNAVAILABLE'})

    client = _make_client(handler)
    with pytest.raises(B2BUnavailableError):
        await client.reserve(idempotency_key=uuid4(), items=[])


@pytest.mark.anyio
async def test_reserve_network_error_raises_b2b_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('cannot connect')

    client = _make_client(handler)
    with pytest.raises(B2BUnavailableError):
        await client.reserve(idempotency_key=uuid4(), items=[])


@pytest.mark.anyio
async def test_get_skus_info_parses_items():
    sku_id = uuid4()
    product_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                'items': [
                    {
                        'id': str(sku_id),
                        'product_id': str(product_id),
                        'product_title': 'Phone',
                        'name': '128GB',
                        'price': 12_999_000,
                    }
                ],
            },
        )

    client = _make_client(handler)
    info = await client.get_skus_info([sku_id])
    assert sku_id in info
    assert info[sku_id]['price'] == 12_999_000


@pytest.mark.anyio
async def test_unreserve_5xx_raises_b2b_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={'code': 'BAD_GATEWAY'})

    client = _make_client(handler)
    with pytest.raises(B2BUnavailableError):
        await client.unreserve(idempotency_key=uuid4(), items=[])


@pytest.mark.anyio
async def test_fulfill_returns_ok():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'fulfilled': True})

    client = _make_client(handler)
    res = await client.fulfill(order_id=uuid4(), items=[])
    assert res == {'fulfilled': True}
