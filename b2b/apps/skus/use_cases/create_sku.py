"""US-B2B-02: создание SKU продавцом.

Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#add-sku):

- product_id должен принадлежать seller'у из JWT (защита от IDOR) -> иначе 403.
- product.status == HARD_BLOCKED -> 403 (запрещено добавлять SKU).
- Если это первый SKU товара и status == CREATED:
    1. product.status переходит в ON_MODERATION.
    2. В outbox enqueue-ится событие CREATED с target_service=moderation;
       payload — полный снимок продукта (title, description, category_id, slug,
       images, characteristics) + список skus содержащий только что созданный SKU.
- Если уже есть SKU — НЕ меняем статус, НЕ кладём событие в outbox.
- Минимум 1 изображение обязательно (на уровне use-case → 400).
- discount — целое число в копейках, не процент.
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
    ProductNotFoundError,
    SKUHardBlockedError,
    SKUImagesRequiredError,
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
    SKUCreateSchema,
    SKUImageCreateSchema,
    SKUImageReadSchema,
    SKUReadSchema,
)
from apps.skus.schemas.request import SKUCreateRequestSchema
from apps.skus.schemas.response import (
    SKUCharacteristicResponseSchema,
    SKUImageResponseSchema,
    SKUResponseSchema,
)
from shared.auth_lib import AuthenticatedUserSchema
from shared.outbox import OutboxEnqueueSchema
from shared.types import ServiceName


class CreateSKUUseCase:
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
        data: SKUCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> SKUResponseSchema:
        if not data.images:
            raise SKUImagesRequiredError()

        product = await self._load_product(data.product_id, current_user)

        sku = await self.sku_repository.create(
            SKUCreateSchema(
                product_id=product.id,
                name=data.name,
                price=data.price,
                cost_price=data.cost_price,
                discount=data.discount,
                article=data.article,
                active_quantity=data.stock_quantity,
                reserved_quantity=0,
            )
        )

        images = [
            await self.sku_image_repository.create(
                SKUImageCreateSchema(sku_id=sku.id, url=image.url, ordering=image.ordering)
            )
            for image in data.images
        ]

        characteristics = [
            await self.sku_characteristic_repository.create(
                SKUCharacteristicValueCreateSchema(sku_id=sku.id, name=ch.name, value=ch.value)
            )
            for ch in data.characteristics
        ]

        # Side-effect: первый SKU + CREATED-товар → ON_MODERATION + outbox CREATED.
        is_first_sku = await self._is_first_sku(product.id)
        if is_first_sku and product.status == ProductStatus.CREATED:
            await self.product_repository.update(ProductUpdateSchema(id=product.id, status=ProductStatus.ON_MODERATION))
            await self._enqueue_created_event(product, sku, images, characteristics)

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
            stock_quantity=sku.stock_quantity,
            images=[SKUImageResponseSchema(id=i.id, url=i.url, ordering=i.ordering) for i in images],
            characteristics=[
                SKUCharacteristicResponseSchema(id=c.id, name=c.name, value=c.value) for c in characteristics
            ],
            created_at=sku.created_at,
            updated_at=sku.updated_at,
        )

    async def _load_product(self, product_id: UUID, current_user: AuthenticatedUserSchema) -> ProductReadSchema:
        product = await self.product_repository.get_or_none(product_id)
        if product is None:
            raise ProductNotFoundError()
        if product.seller_id != current_user.id:
            raise SKUNotOwnerError()
        if product.status == ProductStatus.HARD_BLOCKED:
            raise SKUHardBlockedError()
        return product

    async def _is_first_sku(self, product_id: UUID) -> bool:
        """Это первый SKU? Считаем количество SKU у товара.

        Метод вызывается ПОСЛЕ того, как только что созданный SKU уже записан в БД,
        поэтому "первый SKU" == count == 1.

        В наивной реализации (без транзакционной блокировки) теоретически возможна
        гонка двух одновременных POST. Для первой итерации принимаем риск:
        worst-case — отправится два CREATED-события в moderation, дедупликация
        — на стороне получателя по `idempotency_key`/`product_id`.
        """
        count = await self.sku_repository.count_by_product(product_id)
        return count == 1

    async def _enqueue_created_event(
        self,
        product: ProductReadSchema,
        sku: SKUReadSchema,
        sku_images: list[SKUImageReadSchema],
        sku_characteristics: list[SKUCharacteristicValueReadSchema],
    ) -> None:
        product_images = await self.product_image_repository.list_by_product(product.id)
        product_characteristics = await self.product_characteristic_repository.list_by_product(product.id)

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
            'skus': [
                {
                    'id': str(sku.id),
                    'name': sku.name,
                    'price': sku.price,
                    'cost_price': sku.cost_price,
                    'discount': sku.discount,
                    'article': sku.article,
                    'active_quantity': sku.active_quantity,
                    'reserved_quantity': sku.reserved_quantity,
                    'stock_quantity': sku.stock_quantity,
                    'images': [{'id': str(i.id), 'url': i.url, 'ordering': i.ordering} for i in sku_images],
                    'characteristics': [
                        {'id': str(c.id), 'name': c.name, 'value': c.value} for c in sku_characteristics
                    ],
                }
            ],
        }

        await self.outbox_repository.enqueue_in_new_transaction(
            OutboxEnqueueSchema(
                idempotency_key=uuid4(),
                event_type='CREATED',
                target_service=ServiceName.MODERATION,
                payload=payload,
            )
        )
