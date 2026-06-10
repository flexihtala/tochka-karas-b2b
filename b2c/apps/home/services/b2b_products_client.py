"""B2BProductsClient — batch-обогащение товаров для подборок b2c.

Дизайн:
- POST /api/v1/public/products/batch с {"product_ids": [...]} → bare list карточек
  (контракт b2b/apps/public: BatchProductsRequestSchema → list[ProductPublicResponseSchema]).
- b2b возвращает ТОЛЬКО доступные продукты (статус MODERATED, не deleted, не BLOCKED).
  Те id, что не вернулись, b2c считает unavailable.
- Поля карточки маппятся: price ← min_price, image_url ← cover_image.
- Под капотом — `shared.http_clients.ServiceClient`, с X-Service-Key.
"""

from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, TypeAdapter

from shared.http_clients import ServiceClient


class B2BProductSchema(BaseModel):
    """Минимальная карточка товара, нужная homepage-подборкам."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    title: str
    slug: str
    price: int | None = Field(default=None, validation_alias=AliasChoices('price', 'min_price'))
    image_url: str | None = Field(default=None, validation_alias=AliasChoices('image_url', 'cover_image'))


_batch_list_adapter = TypeAdapter(list[B2BProductSchema])


class B2BProductsClient:
    """Тонкая доменная обёртка над ServiceClient для запроса карточек товаров."""

    def __init__(self, service_client: ServiceClient):
        self.service_client = service_client

    async def fetch_batch(self, product_ids: list[UUID]) -> list[B2BProductSchema]:
        """Пакетно возвращает доступные товары.

        Семантика «недоступности» — b2b просто не вернёт id блокированных/удалённых,
        вызывающий код должен дозаполнить unavailable_ids разницей `requested - returned`.
        """
        if not product_ids:
            return []

        payload = {'product_ids': [str(pid) for pid in product_ids]}
        response = await self.service_client.post('/api/v1/public/products/batch', json=payload)
        return _batch_list_adapter.validate_python(response)
