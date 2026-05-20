"""B2BProductsClient — batch-обогащение товаров для подборок b2c.

Дизайн:
- POST /api/v1/products/batch с {"ids": [...]} → {"items": [...]}.
- b2b возвращает ТОЛЬКО доступные продукты (статус MODERATED, не deleted, не BLOCKED).
  Те id, что не вернулись, b2c считает unavailable.
- Под капотом — `shared.http_clients.ServiceClient`, с X-Service-Key.
"""

from uuid import UUID

from pydantic import BaseModel

from shared.http_clients import ServiceClient


class B2BProductSchema(BaseModel):
    """Минимальная карточка товара, нужная homepage-подборкам."""

    id: UUID
    title: str
    slug: str
    price: float | None = None
    image_url: str | None = None


class B2BProductsBatchResponseSchema(BaseModel):
    items: list[B2BProductSchema]


class B2BProductsClient:
    """Тонкий доменный обёртка над ServiceClient для запроса карточек товаров."""

    def __init__(self, service_client: ServiceClient):
        self.service_client = service_client

    async def fetch_batch(self, product_ids: list[UUID]) -> list[B2BProductSchema]:
        """Пакетно возвращает доступные товары.

        Семантика «недоступности» — b2b просто не вернёт id блокированных/удалённых,
        вызывающий код должен дозаполнить unavailable_ids разницей `requested - returned`.
        """
        if not product_ids:
            return []

        payload = {'ids': [str(pid) for pid in product_ids]}
        response = await self.service_client.post('/api/v1/products/batch', json=payload)
        parsed = B2BProductsBatchResponseSchema.model_validate(response)
        return parsed.items
