"""ModerationB2BClient — обёртка над shared.http_clients.ServiceClient для B2B.

Moderation хранит свои данные в собственной БД и обращается к B2B **только по API**.
Этот клиент инкапсулирует пути/имена параметров и маппинг ошибок в доменные:

- GET /api/v1/products/{product_id} — карточка товара (с массивом `skus`).
  - 404 → None (товар удалён/не найден);
  - 5xx / connection / timeout → B2BUnavailableError (503 наружу);
  - 2xx → распарсенный dict товара.

Заголовок X-Service-Key проставляет сам ServiceClient (mod_to_b2b_key).
"""

from typing import Any
from uuid import UUID

import httpx

from apps.tickets.errors import B2BUnavailableError
from shared.http_clients import ServiceClient, ServiceClientError


class ModerationB2BClient:
    """Тонкая обёртка над ServiceClient: маршрутизация ошибок B2B в доменные."""

    def __init__(self, service_client: ServiceClient):
        self.service_client = service_client

    async def get_product(self, product_id: UUID) -> dict[str, Any] | None:
        """GET /api/v1/products/{product_id} — карточка товара с массивом `skus`.

        Возвращает распарсенный dict товара, либо None если B2B ответил 404
        (товар удалён/не существует). На 5xx/сетевой сбой поднимает
        B2BUnavailableError → approve вернёт 503, статус тикета останется IN_REVIEW.
        """
        try:
            return await self.service_client.get(f'/api/v1/products/{product_id}')
        except ServiceClientError as exc:
            if exc.status_code == 404:
                return None
            if exc.status_code >= 500:
                raise B2BUnavailableError() from exc
            raise
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise B2BUnavailableError() from exc
