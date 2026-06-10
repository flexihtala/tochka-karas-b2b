from uuid import UUID

from apps.products.enums import ProductStatus
from apps.products.errors import ProductNotFoundError
from apps.products.repositories import (
    CharacteristicValueRepository,
    ProductImageRepository,
    ProductRepository,
)
from apps.products.schemas.db import ProductReadSchema
from apps.products.schemas.response import (
    BlockingReasonSchema,
    CharacteristicResponseSchema,
    FieldReportSchema,
    ProductDetailResponseSchema,
    ProductImageResponseSchema,
)
from apps.skus.repositories import (
    SKUCharacteristicValueRepository,
    SKUImageRepository,
    SKURepository,
)
from apps.skus.schemas.response import (
    SKUCharacteristicResponseSchema,
    SKUImageResponseSchema,
    SKUResponseSchema,
)
from shared.auth_lib import AuthenticatedUserSchema

#: Статусы, при которых товар считается заблокированным (флаг ``blocked`` в карточке).
_BLOCKED_STATUSES = frozenset({ProductStatus.BLOCKED, ProductStatus.HARD_BLOCKED})


class GetProductUseCase:
    """B2B-5: просмотр карточки товара продавцом (seller cabinet).

    Бизнес-правила (см. neomarket-canon/flows/b2b-flows.md#view-product):

    - seller_id берётся ТОЛЬКО из JWT claims (никогда из query/headers).
    - **Чужой товар → 404 NOT_FOUND, НЕ 403.** Это сознательное решение: 403
      раскрыл бы факт существования чужого товара (IDOR-by-discovery),
      404 — нет.
    - Несуществующий товар → 404 NOT_FOUND.
    - Soft-deleted товар (deleted=true) виден владельцу — в ответе передаётся
      флаг ``deleted`` (отдельного query ?include_deleted не требуется: данные
      продавцу принадлежат, скрывать от него нет смысла; B2C-режим фильтрует
      такие товары в каталоге отдельно).
    - Ответ — ``ProductDetailResponse`` (openapi): флаг ``blocked``, объект
      ``blocking_reason`` ({id, title, comment}) и массив ``field_reports``.
      ``blocking_reason`` непустой только для BLOCKED/HARD_BLOCKED товаров.
      ``blocking_reason_title`` / ``field_reports`` заполняются flow модерации
      (US-B2B-09, обработчик MODERATED/BLOCKED-событий); до этого момента
      хранятся пустыми, и GET читает их как есть.
    - MODERATED/любой товар: полный payload, в т.ч. cost_price/reserved_quantity
      на уровне SKU. SKU подгружаются через ``_load_skus`` — полные seller-view
      SKU с картинками и характеристиками.

    Авторизация роли (SELLER) выполняется в роутере через ``require_role``;
    use-case считает ``current_user`` уже валидированным.
    """

    def __init__(
        self,
        product_repository: ProductRepository,
        image_repository: ProductImageRepository,
        characteristic_repository: CharacteristicValueRepository,
        sku_repository: SKURepository,
        sku_image_repository: SKUImageRepository,
        sku_characteristic_repository: SKUCharacteristicValueRepository,
    ):
        self.product_repository = product_repository
        self.image_repository = image_repository
        self.characteristic_repository = characteristic_repository
        self.sku_repository = sku_repository
        self.sku_image_repository = sku_image_repository
        self.sku_characteristic_repository = sku_characteristic_repository

    async def _load_skus(self, product_id: UUID) -> list[SKUResponseSchema]:
        """Загружает полные SKU товара (seller-view) с картинками и характеристиками.

        Для каждого SKU дополнительно подтягиваются его изображения и
        характеристики из соответствующих репозиториев. ``stock_quantity`` —
        derived-свойство SKU (active + reserved), уже посчитано в read-схеме.
        """
        skus = await self.sku_repository.list_full_by_product(product_id)
        result: list[SKUResponseSchema] = []
        for sku in skus:
            images = await self.sku_image_repository.list_by_sku(sku.id)
            characteristics = await self.sku_characteristic_repository.list_by_sku(sku.id)
            result.append(
                SKUResponseSchema(
                    id=sku.id,
                    product_id=sku.product_id,
                    name=sku.name,
                    price=sku.price,
                    discount=sku.discount,
                    cost_price=sku.cost_price,
                    stock_quantity=sku.stock_quantity,
                    active_quantity=sku.active_quantity,
                    reserved_quantity=sku.reserved_quantity,
                    article=sku.article,
                    images=[
                        SKUImageResponseSchema(id=image.id, url=image.url, ordering=image.ordering) for image in images
                    ],
                    characteristics=[
                        SKUCharacteristicResponseSchema(id=c.id, name=c.name, value=c.value) for c in characteristics
                    ],
                    created_at=sku.created_at,
                    updated_at=sku.updated_at,
                )
            )
        return result

    @staticmethod
    def _build_blocking_reason(product: ProductReadSchema) -> BlockingReasonSchema | None:
        """Собирает объект blocking_reason из плоских полей продукта.

        Возвращает None для незаблокированных товаров. Для заблокированных —
        {id, title, comment}, где id берётся из ``blocking_reason_id``
        (фолбэк на нулевой UUID, если ещё не проставлен), title/comment — из
        ``blocking_reason_title`` / ``moderator_comment`` (пустая строка, если
        flow модерации ещё не заполнил).
        """
        if product.status not in _BLOCKED_STATUSES:
            return None
        return BlockingReasonSchema(
            id=product.blocking_reason_id or UUID(int=0),
            title=product.blocking_reason_title or '',
            comment=product.moderator_comment or '',
        )

    async def __call__(
        self,
        product_id: UUID,
        current_user: AuthenticatedUserSchema,
    ) -> ProductDetailResponseSchema:
        product = await self.product_repository.get_or_none(product_id)
        if product is None:
            # Несуществующий товар.
            raise ProductNotFoundError()
        if product.seller_id != current_user.id:
            # Чужой товар. Не 403 — иначе клиент может перебором UUID
            # отличить «404 не существует» от «403 чужой» и составить карту
            # принадлежности (IDOR-by-discovery).
            raise ProductNotFoundError()

        images = await self.image_repository.list_by_product(product.id)
        characteristics = await self.characteristic_repository.list_by_product(product.id)
        skus = await self._load_skus(product.id)

        return ProductDetailResponseSchema(
            id=product.id,
            seller_id=product.seller_id,
            category_id=product.category_id,
            title=product.title,
            slug=product.slug,
            description=product.description,
            status=product.status,
            deleted=product.deleted,
            images=[
                ProductImageResponseSchema(id=image.id, url=image.url, ordering=image.ordering) for image in images
            ],
            characteristics=[
                CharacteristicResponseSchema(id=characteristic.id, name=characteristic.name, value=characteristic.value)
                for characteristic in characteristics
            ],
            skus=skus,
            created_at=product.created_at,
            updated_at=product.updated_at,
            blocked=product.status in _BLOCKED_STATUSES,
            blocking_reason=self._build_blocking_reason(product),
            field_reports=[FieldReportSchema(**report) for report in (product.field_reports or [])],
        )
