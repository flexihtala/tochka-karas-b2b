"""Тесты B2BProductsClient через httpx MockTransport — без реального B2B-сервиса."""

from uuid import uuid4

import httpx
import pytest

from apps.favorites.use_cases import B2BProductsClient
from shared.http_clients import ServiceClient, ServiceClientError


def _make_client(handler) -> B2BProductsClient:
    transport = httpx.MockTransport(handler)
    service_client = ServiceClient(base_url='http://b2b-test', service_key='test-key', transport=transport)
    return B2BProductsClient(service_client=service_client)


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

    client = _make_client(handler)
    result = await client.list_products_by_ids([pid_a, pid_b])

    assert {p['id'] for p in result} == {str(pid_a), str(pid_b)}


@pytest.mark.anyio
async def test_b2b_products_client_returns_empty_for_empty_ids():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - не вызывается
        raise AssertionError('B2B не должен вызываться при пустом списке ids')

    client = _make_client(handler)
    assert await client.list_products_by_ids([]) == []


@pytest.mark.anyio
async def test_b2b_products_client_raises_service_client_error_on_5xx():
    """Транспортная ошибка пробрасывается как есть — интерпретацию
    (503 на PUT vs деградация GET-списка) делают use-case'ы.
    """

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={'error': {'code': 'SERVICE_UNAVAILABLE', 'message': 'down'}})

    client = _make_client(handler)

    with pytest.raises(ServiceClientError):
        await client.list_products_by_ids([uuid4()])


@pytest.mark.anyio
async def test_b2b_products_client_excludes_non_dict_items_defensively():
    """Если B2B вернёт payload без 'items' или со 'странными' элементами — не падать."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'items': 'broken'})

    client = _make_client(handler)
    assert await client.list_products_by_ids([uuid4()]) == []
