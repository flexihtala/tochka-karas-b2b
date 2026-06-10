"""US-B2B-07: POST /public/products/batch — карточки по списку product_id.

Используется B2C для обогащения корзины / избранного / подборок. Возвращает
ПОЛНЫЕ карточки (ProductPublicResponse) только для видимых товаров. Отсутствующие
и скрытые id молча опускаются (НЕ 404) — B2C трактует их как unavailable.
"""

from typing import Protocol
from uuid import UUID

from apps.public.schemas.response import ProductPublicResponseSchema
from apps.public.use_cases.mappers import to_full_response


class _BatchRepositoryProtocol(Protocol):
    async def list_full_by_ids(self, product_ids: list[UUID]) -> list: ...


class BatchProductsUseCase:
    def __init__(self, repository: _BatchRepositoryProtocol):
        self.repository = repository

    async def __call__(self, *, product_ids: list[UUID]) -> list[ProductPublicResponseSchema]:
        if not product_ids:
            return []
        products = await self.repository.list_full_by_ids(product_ids)
        return [to_full_response(product) for product in products]
