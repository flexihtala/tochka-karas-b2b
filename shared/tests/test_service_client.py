"""Smoke-тесты ServiceClient через httpx MockTransport."""

import httpx
import pytest
from httpx import MockTransport, Request, Response

from shared.http_clients import ServiceClient, ServiceClientError


def _make_client(handler) -> ServiceClient:
    """Создаёт ServiceClient, у которого httpx.AsyncClient уходит на MockTransport."""

    class _PatchedClient(ServiceClient):
        async def _request(self, method, path, *, json=None, params=None, idempotency_key=None):
            url = f'{self.base_url}{path}'
            headers = {'X-Service-Key': self.service_key}
            if idempotency_key:
                headers['Idempotency-Key'] = idempotency_key
            async with httpx.AsyncClient(transport=MockTransport(handler), timeout=self.timeout) as client:
                response = await client.request(method, url, json=json, params=params, headers=headers)
            if response.status_code >= 400:
                try:
                    payload = response.json()
                except ValueError:
                    payload = response.text
                raise ServiceClientError(response.status_code, f'{method} {path} failed', payload)
            if not response.content:
                return {}
            return response.json()

    return _PatchedClient(base_url='http://test', service_key='test-key')


async def test_post_includes_service_key_header():
    captured: dict = {}

    def handler(request: Request) -> Response:
        captured['headers'] = dict(request.headers)
        captured['method'] = request.method
        captured['url'] = str(request.url)
        return Response(200, json={'ok': True})

    client = _make_client(handler)
    result = await client.post('/foo', json={'x': 1}, idempotency_key='k1')

    assert result == {'ok': True}
    assert captured['headers']['x-service-key'] == 'test-key'
    assert captured['headers']['idempotency-key'] == 'k1'
    assert captured['method'] == 'POST'
    assert captured['url'].endswith('/foo')


async def test_error_status_raises():
    def handler(_request: Request) -> Response:
        return Response(503, json={'error': {'code': 'SERVICE_UNAVAILABLE', 'message': 'down'}})

    client = _make_client(handler)
    with pytest.raises(ServiceClientError) as exc_info:
        await client.post('/foo')
    assert exc_info.value.status_code == 503
