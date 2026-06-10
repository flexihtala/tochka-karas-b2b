"""US-B2B-07: GET /public/products/{id}/similar — похожие товары.

Случайная выборка видимых товаров из той же категории (исключая сам товар).
Возвращает КОРОТКИЕ карточки (ProductPublicShortResponse).
"""

from typing import Protocol
from uuid import UUID

from apps.public.schemas.response import ProductPublicShortResponseSchema
from apps.public.use_cases.mappers import to_short_response


class _SimilarRepositoryProtocol(Protocol):
    async def list_similar_short(self, product_id: UUID, *, limit: int) -> list: ...


class GetSimilarProductsUseCase:
    def __init__(self, repository: _SimilarRepositoryProtocol):
        self.repository = repository

    async def __call__(self, product_id: UUID, *, limit: int = 10) -> list[ProductPublicShortResponseSchema]:
        products = await self.repository.list_similar_short(product_id, limit=limit)
        return [to_short_response(product) for product in products]
