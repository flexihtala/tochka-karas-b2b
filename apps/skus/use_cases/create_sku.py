from datetime import UTC, datetime
from uuid import uuid4

from apps.auth.enums import UserRole
from apps.auth.errors import UnauthorizedError
from apps.auth.schemas import AuthenticatedUserSchema
from apps.products.enums import ProductStatus
from apps.products.repositories import ProductRepository
from apps.products.schemas import ProductUpdateSchema
from apps.skus.errors import InvalidSKURequestError, SKUForbiddenError
from apps.skus.repositories import (
    ModerationRepository,
    SKUCharacteristicRepository,
    SKUImageRepository,
    SKURepository,
)
from apps.skus.schemas import (
    SKUCharacteristicCreateSchema,
    SKUCharacteristicResponseSchema,
    SKUCreateRequestSchema,
    SKUCreateSchema,
    SKUImageCreateSchema,
    SKUImageResponseSchema,
    SKUResponseSchema,
)
from apps.skus.schemas.moderation import ProductModerationEventSchema


class CreateSKUUseCase:
    def __init__(
        self,
        sku_repository: SKURepository,
        sku_image_repository: SKUImageRepository,
        sku_characteristic_repository: SKUCharacteristicRepository,
        product_repository: ProductRepository,
        moderation_repository: ModerationRepository,
    ):
        self.sku_repository = sku_repository
        self.sku_image_repository = sku_image_repository
        self.sku_characteristic_repository = sku_characteristic_repository
        self.product_repository = product_repository
        self.moderation_repository = moderation_repository

    async def __call__(
        self,
        data: SKUCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> SKUResponseSchema:
        if current_user.role != UserRole.SELLER:
            raise UnauthorizedError('Требуется роль seller')

        if not data.images:
            raise InvalidSKURequestError('At least one image is required')

        product = await self.product_repository.get_or_none(data.product_id)
        if product is None:
            raise InvalidSKURequestError('Product not found')
        if product.seller_id != current_user.id:
            raise SKUForbiddenError('Cannot add SKU to another seller product')
        if product.status == ProductStatus.HARD_BLOCKED:
            raise SKUForbiddenError('Cannot add SKU to hard blocked product')

        sku_count = await self.sku_repository.count_by_product_id(product.id)
        sku = await self.sku_repository.create(
            SKUCreateSchema(
                product_id=product.id,
                name=data.name.strip(),
                price=data.price,
                stock_quantity=data.stock_quantity,
                article=data.article.strip(),
                cost_price=data.cost_price,
                discount=data.discount,
            )
        )
        images = [
            await self.sku_image_repository.create(
                SKUImageCreateSchema(
                    sku_id=sku.id,
                    url=image.url,
                    ordering=image.ordering,
                )
            )
            for image in data.images
        ]
        characteristics = [
            await self.sku_characteristic_repository.create(
                SKUCharacteristicCreateSchema(
                    sku_id=sku.id,
                    name=characteristic.name,
                    value=characteristic.value,
                )
            )
            for characteristic in data.characteristics
        ]

        if sku_count == 0 and product.status == ProductStatus.CREATED:
            updated_product = await self.product_repository.update(
                ProductUpdateSchema(id=product.id, status=ProductStatus.ON_MODERATION)
            )
            product = updated_product or product
            await self.moderation_repository.send_product_event(
                ProductModerationEventSchema(
                    idempotency_key=uuid4(),
                    product_id=product.id,
                    seller_id=product.seller_id,
                    event='CREATED',
                    date=self._event_date(),
                )
            )

        return SKUResponseSchema(
            id=sku.id,
            product_id=sku.product_id,
            name=sku.name,
            price=sku.price,
            stock_quantity=sku.stock_quantity,
            article=sku.article,
            cost_price=sku.cost_price,
            discount=sku.discount,
            images=[
                SKUImageResponseSchema.model_validate(image) for image in sorted(images, key=lambda item: item.ordering)
            ],
            characteristics=[
                SKUCharacteristicResponseSchema.model_validate(characteristic) for characteristic in characteristics
            ],
            created_at=sku.created_at,
            updated_at=sku.updated_at,
        )

    def _event_date(self) -> str:
        return datetime.now(UTC).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
