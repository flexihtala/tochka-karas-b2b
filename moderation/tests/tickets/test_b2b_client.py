"""Тесты ModerationB2BClient через реальный ServiceClient + httpx.MockTransport.

Мокаем ТОЛЬКО HTTP-границу: ServiceClient(transport=MockTransport) исполняет весь
прод-код (заголовок X-Service-Key, разбор JSON, ServiceClientError), а MockTransport
интерсептит исходящие запросы.
"""

from uuid import uuid4

import httpx
import pytest

from apps.tickets.b2b_client import ModerationB2BClient
from apps.tickets.errors import B2BUnavailableError
from shared.http_clients import ServiceClient


def _make_client(handler) -> ModerationB2BClient:
    transport = httpx.MockTransport(handler)
    sc = ServiceClient(base_url='http://b2b.test', service_key='k', transport=transport)
    return ModerationB2BClient(service_client=sc)


@pytest.mark.anyio
async def test_get_product_hits_path_with_service_key():
    product_id = uuid4()
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen['path'] = request.url.path
        seen['service_key'] = request.headers.get('X-Service-Key')
        return httpx.Response(200, json={'id': str(product_id), 'skus': [{'id': str(uuid4())}]})

    client = _make_client(handler)
    product = await client.get_product(product_id)

    assert seen['path'] == f'/api/v1/products/{product_id}'
    assert seen['service_key'] == 'k'
    assert product is not None
    assert product['skus']


@pytest.mark.anyio
async def test_get_product_404_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={'code': 'PRODUCT_NOT_FOUND'})

    client = _make_client(handler)
    assert await client.get_product(uuid4()) is None


@pytest.mark.anyio
async def test_get_product_5xx_raises_b2b_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={'code': 'UNAVAILABLE'})

    client = _make_client(handler)
    with pytest.raises(B2BUnavailableError):
        await client.get_product(uuid4())


@pytest.mark.anyio
async def test_get_product_network_error_raises_b2b_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('cannot connect')

    client = _make_client(handler)
    with pytest.raises(B2BUnavailableError):
        await client.get_product(uuid4())
