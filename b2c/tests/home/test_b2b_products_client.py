"""Контрактные тесты B2BProductsClient через httpx MockTransport.

Покрытие:
- Корректный path + X-Service-Key + JSON-payload.
- Возврат типизированных карточек.
- Пустой ввод не делает HTTP.
"""

from uuid import uuid4

import httpx
import pytest
from httpx import MockTransport, Request, Response

from apps.home.services import B2BProductsClient, B2BProductSchema
from shared.http_clients import ServiceClient


def _patched_client(handler) -> ServiceClient:
    """Возвращает ServiceClient, чьи HTTP-вызовы маршрутизируются через MockTransport."""

    class _PatchedClient(ServiceClient):
        async def _request(self, method, path, *, json=None, params=None, idempotency_key=None):
            url = f'{self.base_url}{path}'
            headers = {'X-Service-Key': self.service_key}
            if idempotency_key:
                headers['Idempotency-Key'] = idempotency_key
            async with httpx.AsyncClient(transport=MockTransport(handler), timeout=self.timeout) as client:
                response = await client.request(method, url, json=json, params=params, headers=headers)
            if response.status_code >= 400:
                from shared.http_clients import ServiceClientError

                try:
                    payload = response.json()
                except ValueError:
                    payload = response.text
                raise ServiceClientError(response.status_code, f'{method} {path} failed', payload)
            if not response.content:
                return {}
            return response.json()

    return _PatchedClient(base_url='http://b2b.test', service_key='dev-b2c-to-b2b-key-change-me')


@pytest.mark.anyio
async def test_fetch_batch_calls_b2b_with_ids_and_returns_products():
    pid_a = uuid4()
    pid_b = uuid4()
    captured: dict = {}

    def handler(request: Request) -> Response:
        captured['method'] = request.method
        captured['url'] = str(request.url)
        captured['headers'] = dict(request.headers)
        captured['body'] = request.content.decode()
        return Response(
            200,
            json={
                'items': [
                    {
                        'id': str(pid_a),
                        'title': 'Apple',
                        'slug': 'apple',
                        'price': 99.5,
                        'image_url': 'https://cdn.b2b/apple.png',
                    },
                    {
                        'id': str(pid_b),
                        'title': 'Banana',
                        'slug': 'banana',
                        'price': None,
                        'image_url': None,
                    },
                ]
            },
        )

    client = B2BProductsClient(service_client=_patched_client(handler))
    result = await client.fetch_batch([pid_a, pid_b])

    assert isinstance(result[0], B2BProductSchema)
    assert {p.id for p in result} == {pid_a, pid_b}
    assert result[0].slug == 'apple'
    assert captured['method'] == 'POST'
    assert captured['url'].endswith('/api/v1/products/batch')
    assert captured['headers']['x-service-key'] == 'dev-b2c-to-b2b-key-change-me'
    assert str(pid_a) in captured['body']
    assert str(pid_b) in captured['body']


@pytest.mark.anyio
async def test_fetch_batch_empty_list_short_circuits_without_http():
    calls: list[Request] = []

    def handler(request: Request) -> Response:
        calls.append(request)
        return Response(500, json={})

    client = B2BProductsClient(service_client=_patched_client(handler))
    result = await client.fetch_batch([])

    assert result == []
    assert calls == []
