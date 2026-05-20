import re
import unicodedata
from uuid import uuid4

from apps.categories.repositories import CategoryRepository
from apps.products.enums import ProductStatus
from apps.products.errors import CategoryNotFoundError, ImagesRequiredError
from apps.products.repositories import (
    CharacteristicValueRepository,
    ProductImageRepository,
    ProductRepository,
)
from apps.products.schemas.db import (
    CharacteristicValueCreateSchema,
    ProductCreateSchema,
    ProductImageCreateSchema,
)
from apps.products.schemas.request import ProductCreateRequestSchema
from apps.products.schemas.response import (
    CharacteristicResponseSchema,
    ProductImageResponseSchema,
    ProductResponseSchema,
)
from shared.auth_lib import AuthenticatedUserSchema


def _slugify(value: str) -> str:
    """Простая нормализация slug. Если пользовательский slug не передан — генерируем из title."""
    normalized = unicodedata.normalize('NFKD', value)
    ascii_only = normalized.encode('ascii', 'ignore').decode('ascii').lower()
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_only).strip('-')
    return slug or uuid4().hex[:12]


class CreateProductUseCase:
    """B2B-1: создание товара продавцом.

    Бизнес-правила:
    - seller_id ВСЕГДА берётся из JWT-клеймов, никогда не из тела (защита от IDOR).
    - Требуется хотя бы одно изображение → иначе 400 INVALID_REQUEST.
    - category_id обязан существовать в справочнике → иначе 400 INVALID_REQUEST.
    - Товар создаётся со статусом CREATED. На модерацию НЕ идёт (нужен SKU, см. US-B2B-02).
    - В ответе skus всегда [].
    """

    def __init__(
        self,
        product_repository: ProductRepository,
        image_repository: ProductImageRepository,
        characteristic_repository: CharacteristicValueRepository,
        category_repository: CategoryRepository,
    ):
        self.product_repository = product_repository
        self.image_repository = image_repository
        self.characteristic_repository = characteristic_repository
        self.category_repository = category_repository

    async def __call__(
        self,
        data: ProductCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> ProductResponseSchema:
        if not data.images:
            raise ImagesRequiredError()

        if not await self.category_repository.exists(data.category_id):
            raise CategoryNotFoundError()

        product = await self.product_repository.create(
            ProductCreateSchema(
                seller_id=current_user.id,
                category_id=data.category_id,
                title=data.title,
                slug=data.slug or _slugify(data.title),
                description=data.description,
                status=ProductStatus.CREATED,
                deleted=False,
                blocking_reason_id=None,
                moderator_comment=None,
            )
        )

        images = [
            await self.image_repository.create(
                ProductImageCreateSchema(
                    product_id=product.id,
                    url=image.url,
                    ordering=image.ordering,
                )
            )
            for image in data.images
        ]

        characteristics = [
            await self.characteristic_repository.create(
                CharacteristicValueCreateSchema(
                    product_id=product.id,
                    name=characteristic.name,
                    value=characteristic.value,
                )
            )
            for characteristic in data.characteristics
        ]

        return ProductResponseSchema(
            id=product.id,
            seller_id=product.seller_id,
            category_id=product.category_id,
            title=product.title,
            slug=product.slug,
            description=product.description,
            status=product.status,
            deleted=product.deleted,
            blocking_reason_id=product.blocking_reason_id,
            moderator_comment=product.moderator_comment,
            images=[
                ProductImageResponseSchema(id=image.id, url=image.url, ordering=image.ordering) for image in images
            ],
            characteristics=[
                CharacteristicResponseSchema(id=characteristic.id, name=characteristic.name, value=characteristic.value)
                for characteristic in characteristics
            ],
            skus=[],
            created_at=product.created_at,
            updated_at=product.updated_at,
        )
