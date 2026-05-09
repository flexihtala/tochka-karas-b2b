from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.auth.enums import UserRole
from apps.auth.errors import UnauthorizedError
from apps.auth.schemas import AuthenticatedUserSchema
from apps.products.enums import ProductStatus
from apps.products.errors import ProductNotFoundError
from apps.products.repositories import ProductRepository
from apps.products.schemas import ProductUpdateSchema
from apps.skus.errors import InvalidSKURequestError, SKUForbiddenError, SKUNotFoundError
from apps.skus.repositories import (
    ModerationRepository,
    SKUCharacteristicRepository,
    SKUImageRepository,
    SKURepository,
)
from apps.skus.schemas import (
    SKUCharacteristicCreateSchema,
    SKUCharacteristicResponseSchema,
    SKUEditRequestSchema,
    SKUImageCreateSchema,
    SKUImageResponseSchema,
    SKUResponseSchema,
    SKUUpdateSchema,
)
from apps.skus.schemas.moderation import ProductModerationEventSchema

EDITED_TRIGGER_STATUSES = (ProductStatus.MODERATED, ProductStatus.BLOCKED)


class EditSKUUseCase:
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
        sku_id: UUID,
        data: SKUEditRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> SKUResponseSchema:
        if current_user.role != UserRole.SELLER:
            raise UnauthorizedError('Требуется роль seller')

        sku = await self.sku_repository.get_or_none(sku_id)
        if sku is None:
            raise SKUNotFoundError()

        product = await self.product_repository.get_or_none(sku.product_id)
        if product is None:
            raise ProductNotFoundError()
        if product.seller_id != current_user.id:
            raise SKUForbiddenError('SKU does not belong to the authenticated seller', code='NOT_OWNER')
        if product.status == ProductStatus.HARD_BLOCKED:
            raise SKUForbiddenError('Cannot edit SKU of hard-blocked product')

        if not data.images:
            raise InvalidSKURequestError('At least one image is required')

        previous_status = product.status

        updated_sku = await self.sku_repository.update(
            SKUUpdateSchema(
                id=sku.id,
                name=data.name.strip(),
                price=data.price,
                stock_quantity=data.stock_quantity,
                article=data.article.strip(),
                cost_price=data.cost_price,
                discount=data.discount,
            )
        )
        sku = updated_sku or sku

        await self.sku_image_repository.delete_by_sku_id(sku.id)
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

        await self.sku_characteristic_repository.delete_by_sku_id(sku.id)
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

        if previous_status in EDITED_TRIGGER_STATUSES:
            await self.product_repository.update(ProductUpdateSchema(id=product.id, status=ProductStatus.ON_MODERATION))
            await self.moderation_repository.send_product_event(
                ProductModerationEventSchema(
                    idempotency_key=uuid4(),
                    product_id=product.id,
                    seller_id=product.seller_id,
                    event='EDITED',
                    date=self._event_date(),
                )
            )

        return SKUResponseSchema(
            id=sku.id,
            product_id=sku.product_id,
            name=sku.name,
            price=sku.price,
            stock_quantity=sku.stock_quantity,
            reserved_quantity=sku.reserved_quantity,
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
