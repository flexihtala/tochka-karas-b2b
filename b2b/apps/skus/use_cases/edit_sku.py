"""US-B2B-03: редактирование SKU продавцом.

Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#edit-product):

- Auth: SELLER, ownership проверяется через parent product (`sku.product.seller_id == jwt.user_id`).
- HARD_BLOCKED parent → 403 с code=HARD_BLOCKED.
- reserved_quantity НЕ модифицируется (актив резервов остаётся).
- active_quantity/stock_quantity также не редактируются через этот endpoint
  (приёмка → invoices, расход → reserves; см. canon).
- product_id не меняется (запрещено move-SKU между товарами).
- Если parent.status в {MODERATED, BLOCKED} → product переводим в ON_MODERATION
  и кладём в outbox EDITED.
- images/characteristics — атомарная замена при передаче поля.
"""

from uuid import UUID, uuid4

from apps.outbox.repositories import B2BOutboxRepository
from apps.products.enums import ProductStatus
from apps.products.repositories import (
    CharacteristicValueRepository,
    ProductImageRepository,
    ProductRepository,
)
from apps.products.schemas.db import ProductReadSchema, ProductUpdateSchema
from apps.skus.errors import (
    SKUForbiddenError,
    SKUHardBlockedError,
    SKUImagesRequiredError,
    SKUNotFoundError,
    SKUNotOwnerError,
)
from apps.skus.repositories import (
    SKUCharacteristicValueRepository,
    SKUImageRepository,
    SKURepository,
)
from apps.skus.schemas.db import (
    SKUCharacteristicValueCreateSchema,
    SKUCharacteristicValueReadSchema,
    SKUImageCreateSchema,
    SKUImageReadSchema,
    SKUReadSchema,
    SKUUpdateSchema,
)
from apps.skus.schemas.request import SKUEditRequestSchema
from apps.skus.schemas.response import (
    SKUCharacteristicResponseSchema,
    SKUImageResponseSchema,
    SKUResponseSchema,
)
from shared.auth_lib import AuthenticatedUserSchema
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName

_RETURN_TO_MODERATION_FROM = frozenset({ProductStatus.MODERATED, ProductStatus.BLOCKED})


class EditSKUUseCase:
    def __init__(
        self,
        sku_repository: SKURepository,
        sku_image_repository: SKUImageRepository,
        sku_characteristic_repository: SKUCharacteristicValueRepository,
        product_repository: ProductRepository,
        product_image_repository: ProductImageRepository,
        product_characteristic_repository: CharacteristicValueRepository,
        outbox_repository: B2BOutboxRepository,
    ):
        self.sku_repository = sku_repository
        self.sku_image_repository = sku_image_repository
        self.sku_characteristic_repository = sku_characteristic_repository
        self.product_repository = product_repository
        self.product_image_repository = product_image_repository
        self.product_characteristic_repository = product_characteristic_repository
        self.outbox_repository = outbox_repository

    async def __call__(
        self,
        sku_id: UUID,
        data: SKUEditRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> SKUResponseSchema:
        sku = await self._load_sku(sku_id)
        product = await self._load_parent_and_authorize(sku, current_user)
        self._validate_payload(data)

        sku = await self._apply_field_updates(sku, data)

        if data.images is not None:
            images = await self._replace_images(sku.id, data.images)
        else:
            images = await self.sku_image_repository.list_by_sku(sku.id)

        if data.characteristics is not None:
            characteristics = await self._replace_characteristics(sku.id, data.characteristics)
        else:
            characteristics = await self.sku_characteristic_repository.list_by_sku(sku.id)

        await self._maybe_return_product_to_moderation(product)

        return self._build_response(sku, images, characteristics)

    async def _load_sku(self, sku_id: UUID) -> SKUReadSchema:
        sku = await self.sku_repository.get_or_none(sku_id)
        if sku is None:
            raise SKUNotFoundError()
        return sku

    async def _load_parent_and_authorize(
        self,
        sku: SKUReadSchema,
        current_user: AuthenticatedUserSchema,
    ) -> ProductReadSchema:
        product = await self.product_repository.get_or_none(sku.product_id)
        if product is None:
            # SKU без parent — нарушение инварианта. Возвращаем 404, чтобы не маскировать.
            raise SKUNotFoundError()
        if product.seller_id != current_user.id:
            raise SKUNotOwnerError()
        if product.status == ProductStatus.HARD_BLOCKED:
            raise SKUHardBlockedError()
        return product

    @staticmethod
    def _validate_payload(data: SKUEditRequestSchema) -> None:
        if data.images is not None and len(data.images) == 0:
            raise SKUImagesRequiredError()

    async def _apply_field_updates(self, sku: SKUReadSchema, data: SKUEditRequestSchema) -> SKUReadSchema:
        update_payload: dict = {}
        if data.name is not None:
            update_payload['name'] = data.name
        if data.price is not None:
            update_payload['price'] = data.price
        if data.cost_price is not None:
            update_payload['cost_price'] = data.cost_price
        if data.discount is not None:
            update_payload['discount'] = data.discount
        if data.article is not None:
            update_payload['article'] = data.article

        # ВАЖНО: reserved_quantity и active_quantity НЕ обновляются через edit.

        if not update_payload:
            return sku

        updated = await self.sku_repository.update(SKUUpdateSchema(id=sku.id, **update_payload))
        return updated or sku

    async def _replace_images(self, sku_id: UUID, images: list) -> list[SKUImageReadSchema]:
        await self.sku_image_repository.delete_by_sku(sku_id)
        return [
            await self.sku_image_repository.create(
                SKUImageCreateSchema(sku_id=sku_id, url=image.url, ordering=image.ordering)
            )
            for image in images
        ]

    async def _replace_characteristics(
        self,
        sku_id: UUID,
        characteristics: list,
    ) -> list[SKUCharacteristicValueReadSchema]:
        await self.sku_characteristic_repository.delete_by_sku(sku_id)
        return [
            await self.sku_characteristic_repository.create(
                SKUCharacteristicValueCreateSchema(sku_id=sku_id, name=ch.name, value=ch.value)
            )
            for ch in characteristics
        ]

    async def _maybe_return_product_to_moderation(self, product: ProductReadSchema) -> None:
        if product.status not in _RETURN_TO_MODERATION_FROM:
            return

        await self.product_repository.update(ProductUpdateSchema(id=product.id, status=ProductStatus.ON_MODERATION))
        await self._enqueue_edited_event(product)

    async def _enqueue_edited_event(self, product: ProductReadSchema) -> None:
        product_images = await self.product_image_repository.list_by_product(product.id)
        product_characteristics = await self.product_characteristic_repository.list_by_product(product.id)
        sku_count = await self.sku_repository.count_by_product(product.id)

        payload = {
            'product_id': str(product.id),
            'seller_id': str(product.seller_id),
            'title': product.title,
            'description': product.description,
            'category_id': str(product.category_id),
            'slug': product.slug,
            'images': [{'id': str(image.id), 'url': image.url, 'ordering': image.ordering} for image in product_images],
            'characteristics': [
                {'id': str(ch.id), 'name': ch.name, 'value': ch.value} for ch in product_characteristics
            ],
            'sku_count': sku_count,
        }

        await self.outbox_repository.enqueue_in_new_transaction(
            OutboxEnqueueSchema(
                idempotency_key=uuid4(),
                event_type='EDITED',
                target_service=ServiceName.MODERATION,
                payload=payload,
            )
        )

    @staticmethod
    def _build_response(
        sku: SKUReadSchema,
        images: list[SKUImageReadSchema],
        characteristics: list[SKUCharacteristicValueReadSchema],
    ) -> SKUResponseSchema:
        return SKUResponseSchema(
            id=sku.id,
            product_id=sku.product_id,
            name=sku.name,
            price=sku.price,
            cost_price=sku.cost_price,
            discount=sku.discount,
            article=sku.article,
            active_quantity=sku.active_quantity,
            reserved_quantity=sku.reserved_quantity,
            images=[SKUImageResponseSchema(id=i.id, url=i.url, ordering=i.ordering) for i in images],
            characteristics=[
                SKUCharacteristicResponseSchema(id=c.id, name=c.name, value=c.value) for c in characteristics
            ],
            created_at=sku.created_at,
            updated_at=sku.updated_at,
        )


# Re-export for tests / depends. SKUForbiddenError is referenced indirectly via tests.
__all__ = ['EditSKUUseCase', 'SKUForbiddenError']
