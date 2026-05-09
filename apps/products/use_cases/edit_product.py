from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.auth.enums import UserRole
from apps.auth.errors import UnauthorizedError
from apps.auth.schemas.token import AuthenticatedUserSchema
from apps.products.enums import ProductStatus
from apps.products.errors import InvalidProductRequestError, ProductForbiddenError, ProductNotFoundError
from apps.products.repositories import (
    CategoryRepository,
    ProductCharacteristicRepository,
    ProductImageRepository,
    ProductRepository,
)
from apps.products.schemas.product import (
    ProductCharacteristicCreateSchema,
    ProductImageCreateSchema,
    ProductUpdateSchema,
)
from apps.products.schemas.request import ProductEditRequestSchema
from apps.products.schemas.response import (
    ProductCharacteristicResponseSchema,
    ProductImageResponseSchema,
    ProductResponseSchema,
)
from apps.products.use_cases._validators import validate_category_id, validate_description, validate_title
from apps.skus.repositories import ModerationRepository
from apps.skus.schemas.moderation import ProductModerationEventSchema

EDITED_TRIGGER_STATUSES = (ProductStatus.MODERATED, ProductStatus.BLOCKED)


class EditProductUseCase:
    def __init__(
        self,
        product_repository: ProductRepository,
        product_image_repository: ProductImageRepository,
        product_characteristic_repository: ProductCharacteristicRepository,
        category_repository: CategoryRepository,
        moderation_repository: ModerationRepository,
    ):
        self.product_repository = product_repository
        self.product_image_repository = product_image_repository
        self.product_characteristic_repository = product_characteristic_repository
        self.category_repository = category_repository
        self.moderation_repository = moderation_repository

    async def __call__(
        self,
        product_id: UUID,
        data: ProductEditRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> ProductResponseSchema:
        if current_user.role != UserRole.SELLER:
            raise UnauthorizedError('Требуется роль seller')

        product = await self.product_repository.get_or_none(product_id)
        if product is None:
            raise ProductNotFoundError()
        if product.seller_id != current_user.id:
            raise ProductForbiddenError('NOT_OWNER', 'Product does not belong to the authenticated seller')
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ProductForbiddenError('FORBIDDEN', 'Cannot edit hard-blocked product')

        title = validate_title(data.title)
        description = validate_description(data.description)
        category_id = validate_category_id(data.category_id)

        if not data.images:
            raise InvalidProductRequestError('At least one image is required')

        category = await self.category_repository.get_or_none(category_id)
        if category is None:
            raise InvalidProductRequestError('Category not found')

        previous_status = product.status
        new_status = ProductStatus.ON_MODERATION if previous_status in EDITED_TRIGGER_STATUSES else previous_status

        updated_product = await self.product_repository.update(
            ProductUpdateSchema(
                id=product.id,
                title=title,
                description=description,
                category_id=category_id,
                status=new_status,
            )
        )
        product = updated_product or product

        await self.product_image_repository.delete_by_product_id(product.id)
        images = [
            await self.product_image_repository.create(
                ProductImageCreateSchema(
                    product_id=product.id,
                    url=image.url,
                    ordering=image.ordering,
                )
            )
            for image in data.images
        ]

        await self.product_characteristic_repository.delete_by_product_id(product.id)
        characteristics = [
            await self.product_characteristic_repository.create(
                ProductCharacteristicCreateSchema(
                    product_id=product.id,
                    name=characteristic.name,
                    value=characteristic.value,
                )
            )
            for characteristic in data.characteristics
        ]

        if previous_status in EDITED_TRIGGER_STATUSES:
            await self.moderation_repository.send_product_event(
                ProductModerationEventSchema(
                    idempotency_key=uuid4(),
                    product_id=product.id,
                    seller_id=product.seller_id,
                    event='EDITED',
                    date=self._event_date(),
                )
            )

        return ProductResponseSchema(
            id=product.id,
            seller_id=product.seller_id,
            category_id=product.category_id,
            title=product.title,
            description=product.description,
            status=product.status,
            created_at=product.created_at,
            updated_at=product.updated_at,
            images=[
                ProductImageResponseSchema.model_validate(image)
                for image in sorted(images, key=lambda item: item.ordering)
            ],
            characteristics=[ProductCharacteristicResponseSchema.model_validate(item) for item in characteristics],
            skus=[],
        )

    def _event_date(self) -> str:
        return datetime.now(UTC).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
