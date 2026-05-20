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
    """HTTP-клиент к одному сервису (один base_url + один X-Service-Key)."""

    def __init__(self, base_url: str, service_key: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip('/')
        self.service_key = service_key
        self.timeout = timeout

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

        async with httpx.AsyncClient(timeout=self.timeout) as client:
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
