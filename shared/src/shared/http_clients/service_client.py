"""ServiceClient — httpx-обёртка для service-to-service вызовов с X-Service-Key.

Все межсервисные вызовы должны идти через этот класс. Идемпотентные операции
поддерживают `idempotency_key` в payload — он же используется для записи в outbox.
"""

from typing import Any

import httpx


class ServiceClientError(Exception):
    """HTTP-ответ от target service != 2xx."""

    def __init__(self, status_code: int, message: str, payload: Any = None):
        super().__init__(f'{status_code}: {message}')
        self.status_code = status_code
        self.payload = payload


class ServiceClient:
    """HTTP-клиент к одному сервису (один base_url + один X-Service-Key).

    `transport` опциональный: тесты могут передать `httpx.MockTransport`,
    чтобы интерсептить исходящие запросы — при этом весь остальной код
    (заголовки, разбор JSON, ServiceClientError) выполняется как в проде.
    """

    def __init__(
        self,
        base_url: str,
        service_key: str,
        timeout: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip('/')
        self.service_key = service_key
        self.timeout = timeout
        self.transport = transport

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

        client_kwargs: dict[str, Any] = {'timeout': self.timeout}
        if self.transport is not None:
            client_kwargs['transport'] = self.transport

        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.request(method, url, json=json, params=params, headers=headers)

        if response.status_code >= 400:
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

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request('GET', path, params=params)

    async def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return await self._request('POST', path, json=json, idempotency_key=idempotency_key)
