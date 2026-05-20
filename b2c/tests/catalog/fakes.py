"""Тестовые фейки для catalog: MockTransport-обёртка вокруг ServiceClient.

ServiceClient через httpx.AsyncClient ходит в B2B — в тестах подменяем транспорт
на httpx.MockTransport, чтобы инспектировать запросы и отдавать предсказанные ответы.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from shared.http_clients import ServiceClient


class MockTransportServiceClient(ServiceClient):
    """ServiceClient, использующий httpx.MockTransport вместо реального транспорта."""

    def __init__(
        self,
        handler: Callable[[httpx.Request], httpx.Response],
        base_url: str = 'http://b2b.test',
        service_key: str = 'test-key',
    ):
        super().__init__(base_url=base_url, service_key=service_key)
        self.transport = httpx.MockTransport(handler)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        url = f'{self.base_url}{path}'
        headers = {'X-Service-Key': self.service_key}
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key

        async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
            response = await client.request(method, url, json=json, params=params, headers=headers)

        if response.status_code >= 400:
            from shared.http_clients.service_client import ServiceClientError

            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            raise ServiceClientError(
                status_code=response.status_code,
                message=f'{method} {path} failed',
                payload=payload,
            )

        if not response.content:
            return {}
        return response.json()  # type: ignore[no-any-return]


def make_handler(
    responses: dict[str, tuple[int, dict[str, Any] | None]],
    on_request: Callable[[httpx.Request], None] | None = None,
) -> Callable[[httpx.Request], Awaitable[httpx.Response] | httpx.Response]:
    """Builder для handler-функции.

    responses: { 'GET /api/v1/catalog/products': (200, {...}) }.
    on_request: optional callback для записи запросов.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if on_request is not None:
            on_request(request)
        key = f'{request.method} {request.url.path}'
        if key not in responses:
            return httpx.Response(status_code=500, json={'code': 'INTERNAL', 'message': 'no mock'})
        status_code, payload = responses[key]
        if payload is None:
            return httpx.Response(status_code=status_code)
        return httpx.Response(status_code=status_code, json=payload)

    return handler
