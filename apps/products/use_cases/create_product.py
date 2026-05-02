from uuid import UUID

from apps.auth.enums import UserRole
from apps.auth.errors import UnauthorizedError
from apps.auth.schemas.token import AuthenticatedUserSchema
from apps.products.enums import ProductStatus
from apps.products.errors import InvalidProductRequestError
from apps.products.repositories import CategoryRepository, ProductRepository
from apps.products.schemas.product import ProductCreateSchema
from apps.products.schemas.request import ProductCreateRequestSchema
from apps.products.schemas.response import (
    ProductCategoryResponseSchema,
    ProductCharacteristicResponseSchema,
    ProductImageResponseSchema,
    ProductResponseSchema,
)


class CreateProductUseCase:
    def __init__(
        self,
        product_repository: ProductRepository,
        category_repository: CategoryRepository,
    ):
        self.product_repository = product_repository
        self.category_repository = category_repository

    async def __call__(
        self,
        data: ProductCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> ProductResponseSchema:
        if current_user.role != UserRole.SELLER:
            raise UnauthorizedError('Требуется роль seller')

        title = self._validate_title(data.title)
        description = self._validate_description(data.description)
        category_id = self._validate_category_id(data.category_id)

        if not data.images:
            raise InvalidProductRequestError('At least one image is required')

        category = await self.category_repository.get_or_none(category_id)
        if category is None:
            raise InvalidProductRequestError('Category not found')

        product = await self.product_repository.create(
            ProductCreateSchema(
                seller_id=current_user.id,
                title=title,
                description=description,
                status=ProductStatus.CREATED,
                category_id=category_id,
                images=[image.model_dump() for image in data.images],
                characteristics=[characteristic.model_dump() for characteristic in data.characteristics],
            )
        )

        return ProductResponseSchema(
            id=product.id,
            title=product.title,
            description=product.description,
            status=product.status,
            deleted=product.deleted,
            blocked=product.blocked,
            category=ProductCategoryResponseSchema(id=category.id, name=category.name),
            images=[
                ProductImageResponseSchema.model_validate(image)
                for image in sorted(product.images, key=lambda item: item['ordering'])
            ],
            characteristics=[
                ProductCharacteristicResponseSchema.model_validate(item) for item in product.characteristics
            ],
            skus=[],
        )

    def _validate_title(self, title: str | None) -> str:
        if title is None or not title.strip():
            raise InvalidProductRequestError('title is required')
        title = title.strip()
        if len(title) > 255:
            raise InvalidProductRequestError('title must be 1-255 characters')
        return title

    def _validate_description(self, description: str | None) -> str:
        if description is None or not description.strip():
            raise InvalidProductRequestError('description is required')
        description = description.strip()
        if len(description) > 5000:
            raise InvalidProductRequestError('description must be 1-5000 characters')
        return description

    def _validate_category_id(self, category_id: str | None) -> UUID:
        if category_id is None:
            raise InvalidProductRequestError('category_id is required')
        try:
            return UUID(category_id)
        except ValueError as exc:
            raise InvalidProductRequestError('category_id must be a valid UUID') from exc
