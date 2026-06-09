"""US-B2B-03: редактирование товара продавцом.

Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#edit-product):

- Auth: SELLER, ownership проверяется явно в use-case (`product.seller_id == jwt.user_id`).
  В режиме OWN-resource любое несовпадение → 403 NOT_OWNER (НЕ 404 — иначе семантика
  раскрывает существование чужих карточек).
- HARD_BLOCKED → 403 с code=HARD_BLOCKED.
- Если product.status в {MODERATED, BLOCKED} → переводим в ON_MODERATION
  и кладём в outbox событие EDITED (target=moderation, idempotency_key=uuid4()).
- Если product.status в {CREATED, ON_MODERATION} → редактировать можно, но
  переход и событие не нужны.
- images/characteristics — атомарная замена: delete_by_product + bulk create
  (только если поле передано в теле; None → не трогаем).
- Валидация полей идентична POST /products.
"""

from uuid import UUID, uuid4

from apps.categories.repositories import CategoryRepository
from apps.outbox.repositories import B2BOutboxRepository
from apps.products.enums import ProductStatus
from apps.products.errors import (
    CategoryNotFoundError,
    ImagesRequiredError,
    ProductHardBlockedError,
    ProductNotFoundError,
    ProductNotOwnerError,
)
from apps.products.repositories import (
    CharacteristicValueRepository,
    ProductImageRepository,
    ProductRepository,
)
from apps.products.schemas.db import (
    CharacteristicValueCreateSchema,
    CharacteristicValueReadSchema,
    ProductImageCreateSchema,
    ProductImageReadSchema,
    ProductReadSchema,
    ProductUpdateSchema,
)
from apps.products.schemas.request import ProductEditRequestSchema
from apps.products.schemas.response import (
    CharacteristicResponseSchema,
    ProductImageResponseSchema,
    ProductResponseSchema,
)
from apps.skus.repositories import SKURepository
from shared.auth_lib import AuthenticatedUserSchema
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName

# Статусы товара, при редактировании которых нужно вернуть на повторную модерацию.
_RETURN_TO_MODERATION_FROM = frozenset({ProductStatus.MODERATED, ProductStatus.BLOCKED})


class EditProductUseCase:
    def __init__(
        self,
        product_repository: ProductRepository,
        image_repository: ProductImageRepository,
        characteristic_repository: CharacteristicValueRepository,
        category_repository: CategoryRepository,
        sku_repository: SKURepository,
        outbox_repository: B2BOutboxRepository,
    ):
        self.product_repository = product_repository
        self.image_repository = image_repository
        self.characteristic_repository = characteristic_repository
        self.category_repository = category_repository
        self.sku_repository = sku_repository
        self.outbox_repository = outbox_repository

    async def __call__(
        self,
        product_id: UUID,
        data: ProductEditRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> ProductResponseSchema:
        product = await self._load_product(product_id, current_user)
        self._validate_payload(data)
        await self._validate_category(data)

        product = await self._apply_field_updates(product, data)

        if data.images is not None:
            images = await self._replace_images(product.id, data.images)
        else:
            images = await self.image_repository.list_by_product(product.id)

        if data.characteristics is not None:
            characteristics = await self._replace_characteristics(product.id, data.characteristics)
        else:
            characteristics = await self.characteristic_repository.list_by_product(product.id)

        product = await self._maybe_return_to_moderation(product)

        return self._build_response(product, images, characteristics)

    async def _load_product(self, product_id: UUID, current_user: AuthenticatedUserSchema) -> ProductReadSchema:
        product = await self.product_repository.get_or_none(product_id)
        if product is None:
            raise ProductNotFoundError()
        if product.seller_id != current_user.id:
            # OWN-mode: чужой товар → 403, не 404. Не раскрываем существование чужих карточек.
            raise ProductNotOwnerError()
        if product.status == ProductStatus.HARD_BLOCKED:
            raise ProductHardBlockedError()
        return product

    @staticmethod
    def _validate_payload(data: ProductEditRequestSchema) -> None:
        # Если images передан, он не должен быть пустым (хотя бы одно изображение).
        if data.images is not None and len(data.images) == 0:
            raise ImagesRequiredError()

    async def _validate_category(self, data: ProductEditRequestSchema) -> None:
        if data.category_id is not None and not await self.category_repository.exists(data.category_id):
            raise CategoryNotFoundError()

    async def _apply_field_updates(
        self,
        product: ProductReadSchema,
        data: ProductEditRequestSchema,
    ) -> ProductReadSchema:
        update_payload: dict = {}
        if data.title is not None:
            update_payload['title'] = data.title
        if data.description is not None:
            update_payload['description'] = data.description
        if data.category_id is not None:
            update_payload['category_id'] = data.category_id
        if data.slug is not None:
            update_payload['slug'] = data.slug

        if not update_payload:
            return product

        updated = await self.product_repository.update(ProductUpdateSchema(id=product.id, **update_payload))
        return updated or product

    async def _replace_images(
        self,
        product_id: UUID,
        images: list,
    ) -> list[ProductImageReadSchema]:
        await self.image_repository.delete_by_product(product_id)
        return [
            await self.image_repository.create(
                ProductImageCreateSchema(product_id=product_id, url=image.url, ordering=image.ordering)
            )
            for image in images
        ]

    async def _replace_characteristics(
        self,
        product_id: UUID,
        characteristics: list,
    ) -> list[CharacteristicValueReadSchema]:
        await self.characteristic_repository.delete_by_product(product_id)
        return [
            await self.characteristic_repository.create(
                CharacteristicValueCreateSchema(product_id=product_id, name=ch.name, value=ch.value)
            )
            for ch in characteristics
        ]

    async def _maybe_return_to_moderation(self, product: ProductReadSchema) -> ProductReadSchema:
        if product.status not in _RETURN_TO_MODERATION_FROM:
            return product

        updated = await self.product_repository.update(
            ProductUpdateSchema(id=product.id, status=ProductStatus.ON_MODERATION)
        )
        product = updated or product.model_copy(update={'status': ProductStatus.ON_MODERATION})

        await self._enqueue_edited_event(product)
        return product

    async def _enqueue_edited_event(self, product: ProductReadSchema) -> None:
        product_images = await self.image_repository.list_by_product(product.id)
        product_characteristics = await self.characteristic_repository.list_by_product(product.id)
        # SKU snapshot нужен модерации, чтобы видеть актуальную сетку артикулов.
        # Берём только те поля, что не зависят от sku_id-аномалий — текущий состав карточки.
        sku_ids = await self.sku_repository.count_by_product(product.id)

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
            'sku_count': sku_ids,
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
        product: ProductReadSchema,
        images: list[ProductImageReadSchema],
        characteristics: list[CharacteristicValueReadSchema],
    ) -> ProductResponseSchema:
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
                CharacteristicResponseSchema(id=ch.id, name=ch.name, value=ch.value) for ch in characteristics
            ],
            skus=[],
            created_at=product.created_at,
            updated_at=product.updated_at,
        )
