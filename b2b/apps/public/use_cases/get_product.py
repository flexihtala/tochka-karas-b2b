"""US-B2B-07: GET /public/products/{id} — полная карточка товара для витрины.

404, если товар не виден (не существует / не MODERATED / deleted / нет остатка).
"""

from typing import Protocol
from uuid import UUID

from apps.public.errors import PublicProductNotFoundError
from apps.public.schemas.response import ProductPublicResponseSchema
from apps.public.use_cases.mappers import to_full_response


class _GetProductRepositoryProtocol(Protocol):
    async def get_full_by_id(self, product_id: UUID): ...


class GetPublicProductUseCase:
    def __init__(self, repository: _GetProductRepositoryProtocol):
        self.repository = repository

    async def __call__(self, product_id: UUID) -> ProductPublicResponseSchema:
        product = await self.repository.get_full_by_id(product_id)
        if product is None:
            raise PublicProductNotFoundError()
        return to_full_response(product)
