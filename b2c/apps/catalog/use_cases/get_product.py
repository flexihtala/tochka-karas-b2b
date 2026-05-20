"""US-CAT-03: GET /api/v1/products/{id} — карточка товара для покупателя.

Проксирует к B2B `/api/v1/catalog/products/{id}` (B2C-view: без cost_price и
reserved_quantity).

Архитектура (ADR — variant 3): отдельный B2B endpoint `/catalog/products/{id}`.
B2B на своей стороне отдаёт только публичные поля. B2C просто mapping в
response-схему + установка in_stock = active_quantity > 0.

Edge cases (canon b2c-catalog-flows.md#b2c-3):
- blocked / deleted / нет SKU с остатком (условие видимости не выполнено) → 404
- Все SKU с нулевым остатком (если открыли прямой ссылкой) — товар отдаётся,
  но все skus с in_stock=false.
"""

from typing import Any
from uuid import UUID

from apps.catalog.clients import B2BCatalogClient
from apps.catalog.errors import CatalogUnavailableError, ProductNotFoundError
from apps.catalog.schemas.response import (
    CatalogProductDetailCharacteristicSchema,
    CatalogProductDetailImageSchema,
    CatalogProductDetailResponseSchema,
    CatalogProductDetailSkuSchema,
)
from shared.http_clients import ServiceClientError


class GetProductUseCase:
    """GET /api/v1/products/{id} — карточка товара для B2C."""

    def __init__(self, b2b_client: B2BCatalogClient):
        self.b2b_client = b2b_client

    async def __call__(self, product_id: UUID) -> CatalogProductDetailResponseSchema:
        try:
            payload = await self.b2b_client.get_product(product_id)
        except ServiceClientError as exc:
            if exc.status_code == 404:
                raise ProductNotFoundError() from exc
            if exc.status_code >= 500:
                raise CatalogUnavailableError() from exc
            raise
        except Exception as exc:
            raise CatalogUnavailableError() from exc

        return self._to_response(payload)

    @staticmethod
    def _to_response(payload: dict[str, Any]) -> CatalogProductDetailResponseSchema:
        """Маппит payload от B2B в b2c-ответ.

        Гарантирует:
        - in_stock = active_quantity > 0 для каждой SKU (не доверяем флагу извне).
        - cost_price / reserved_quantity никогда не попадают в результат — даже
          если B2B по ошибке их отдал, схема их игнорирует (extra='ignore').
        """
        skus_payload = payload.get('skus') or []
        skus: list[CatalogProductDetailSkuSchema] = []
        for sku in skus_payload:
            active_quantity = int(sku.get('active_quantity', 0) or 0)
            sku_image = sku.get('image')
            if sku_image is None:
                images = sku.get('images') or []
                if images:
                    sorted_images = sorted(images, key=lambda i: i.get('ordering', 0))
                    sku_image = sorted_images[0].get('url')
            skus.append(
                CatalogProductDetailSkuSchema(
                    id=sku['id'],
                    name=sku.get('name', ''),
                    price=int(sku.get('price', 0)),
                    discount=int(sku.get('discount', 0) or 0),
                    image=sku_image,
                    active_quantity=active_quantity,
                    in_stock=active_quantity > 0,
                    characteristics=[
                        CatalogProductDetailCharacteristicSchema(name=ch['name'], value=ch['value'])
                        for ch in (sku.get('characteristics') or [])
                    ],
                )
            )

        images = [
            CatalogProductDetailImageSchema(url=img['url'], ordering=img.get('ordering', 0))
            for img in (payload.get('images') or [])
        ]

        return CatalogProductDetailResponseSchema(
            id=payload['id'],
            slug=payload.get('slug'),
            title=payload['title'],
            description=payload.get('description', ''),
            status=payload.get('status'),
            images=images,
            characteristics=[
                CatalogProductDetailCharacteristicSchema(name=ch['name'], value=ch['value'])
                for ch in (payload.get('characteristics') or [])
            ],
            skus=skus,
        )
