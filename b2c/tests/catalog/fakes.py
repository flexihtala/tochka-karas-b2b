"""Тестовые фейки для catalog: httpx.MockTransport вокруг реального ServiceClient.

Мокаем только сетевой транспорт — весь остальной код (заголовки, разбор JSON,
ServiceClientError, бизнес-логика use-case) выполняется как в проде.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from shared.http_clients import ServiceClient


def make_service_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    base_url: str = 'http://b2b.test',
    service_key: str = 'test-key',
) -> ServiceClient:
    """Создаёт реальный ServiceClient с httpx.MockTransport.

    Все исходящие HTTP-запросы перехватываются `handler` — но сам ServiceClient
    выполняется как в проде (заголовки, error-обработка, JSON-парсинг).
    """
    return ServiceClient(
        base_url=base_url,
        service_key=service_key,
        transport=httpx.MockTransport(handler),
    )


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
