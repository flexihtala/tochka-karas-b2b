"""Тесты B2BProductsClient через httpx MockTransport — без реального B2B-сервиса."""

from uuid import uuid4

import httpx
import pytest

from apps.favorites.errors import B2BUnavailableError
from apps.favorites.use_cases import B2BProductsClient
from shared.http_clients import ServiceClient


def _make_client(handler):
    transport = httpx.MockTransport(handler)
    service_client = ServiceClient(base_url='http://b2b-test', service_key='test-key')

    # Подменяем httpx.AsyncClient внутри ServiceClient через monkey-patched factory.
    # Простейший способ — заинжектить transport через подмену метода _request,
    # но проще обернуть send в новом ServiceClient через подкласс.
    class _ServiceClientWithTransport(ServiceClient):
        async def _request(self_inner, method, path, *, json=None, params=None, idempotency_key=None):
            url = f'{self_inner.base_url}{path}'
            headers = {'X-Service-Key': self_inner.service_key}
            if idempotency_key:
                headers['Idempotency-Key'] = idempotency_key
            async with httpx.AsyncClient(transport=transport, timeout=self_inner.timeout) as client:
                response = await client.request(method, url, json=json, params=params, headers=headers)
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

    transport_client = _ServiceClientWithTransport(base_url='http://b2b-test', service_key='test-key')
    return B2BProductsClient(service_client=transport_client), service_client


@pytest.mark.anyio
async def test_b2b_products_client_returns_items_from_b2b():
    pid_a, pid_b = uuid4(), uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == '/api/v1/products'
        assert request.headers['X-Service-Key'] == 'test-key'
        ids_param = request.url.params.get('ids')
        assert ids_param is not None
        ids = set(ids_param.split(','))
        assert ids == {str(pid_a), str(pid_b)}
        return httpx.Response(
            200,
            json={
                'items': [
                    {'id': str(pid_a), 'title': 'A'},
                    {'id': str(pid_b), 'title': 'B'},
                ]
            },
        )

    client, _ = _make_client(handler)
    result = await client.list_products_by_ids([pid_a, pid_b])

    assert {p['id'] for p in result} == {str(pid_a), str(pid_b)}


@pytest.mark.anyio
async def test_b2b_products_client_returns_empty_for_empty_ids():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - не вызывается
        raise AssertionError('B2B не должен вызываться при пустом списке ids')

    client, _ = _make_client(handler)
    assert await client.list_products_by_ids([]) == []


@pytest.mark.anyio
async def test_b2b_products_client_raises_b2b_unavailable_on_5xx():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={'error': {'code': 'SERVICE_UNAVAILABLE', 'message': 'down'}})

    client, _ = _make_client(handler)

    with pytest.raises(B2BUnavailableError):
        await client.list_products_by_ids([uuid4()])


@pytest.mark.anyio
async def test_b2b_products_client_excludes_non_dict_items_defensively():
    """Если B2B вернёт payload без 'items' или со 'странными' элементами — не падать."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'items': 'broken'})

    client, _ = _make_client(handler)
    assert await client.list_products_by_ids([uuid4()]) == []
