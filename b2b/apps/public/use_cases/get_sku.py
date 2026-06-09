"""US-B2B-07: GET /public/skus/{id} — SKU для витрины.

404, если SKU не существует или его товар не виден в каталоге.
Response — SKUPublicResponse (без cost_price / reserved_quantity).
"""

from typing import Protocol
from uuid import UUID

from apps.public.errors import PublicSKUNotFoundError
from apps.public.schemas.response import SKUPublicResponseSchema
from apps.public.use_cases.mappers import to_sku_response


class _GetSKURepositoryProtocol(Protocol):
    async def get_public_sku(self, sku_id: UUID): ...


class GetPublicSKUUseCase:
    def __init__(self, repository: _GetSKURepositoryProtocol):
        self.repository = repository

    async def __call__(self, sku_id: UUID) -> SKUPublicResponseSchema:
        sku = await self.repository.get_public_sku(sku_id)
        if sku is None:
            raise PublicSKUNotFoundError()
        return to_sku_response(sku)
