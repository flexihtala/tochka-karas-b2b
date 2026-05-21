from uuid import UUID

from apps.products.errors import ProductNotFoundError
from apps.products.repositories import (
    CharacteristicValueRepository,
    ProductImageRepository,
    ProductRepository,
)
from apps.products.schemas.response import (
    CharacteristicResponseSchema,
    ProductImageResponseSchema,
    ProductResponseSchema,
    SKUResponseSchema,
)
from shared.auth_lib import AuthenticatedUserSchema


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
    - BLOCKED товар собственный: ответ включает ``blocking_reason_id`` и
      ``moderator_comment``. ``field_reports[]`` опущены в этой итерации —
      модель ProductFieldReport ещё не добавлена; см. PR body.
    - MODERATED товар: полный payload, в т.ч. cost_price/reserved_quantity на
      уровне SKU. SKU-модели пока нет в main (PR #8) → ``skus`` подгружается
      через ``_load_skus`` (placeholder-метод, возвращает [] до мерджа PR #8).

    Авторизация роли (SELLER) выполняется в роутере через ``require_role``;
    use-case считает ``current_user`` уже валидированным.
    """

    def __init__(
        self,
        product_repository: ProductRepository,
        image_repository: ProductImageRepository,
        characteristic_repository: CharacteristicValueRepository,
    ):
        self.product_repository = product_repository
        self.image_repository = image_repository
        self.characteristic_repository = characteristic_repository

    async def _load_skus(self, product_id: UUID) -> list[SKUResponseSchema]:
        """Загружает список SKU для товара.

        Placeholder: SKU-модель пока не в main (живёт в открытом PR #8,
        US-B2B-02). После мерджа PR #8 здесь будет:

            sku_entities = await self.sku_repository.list_by_product(product_id)
            return [
                SKUResponseSchema(
                    id=sku.id,
                    cost_price=sku.cost_price,
                    reserved_quantity=sku.reserved_quantity,
                    ...
                )
                for sku in sku_entities
            ]

        Метод выделен отдельно, чтобы:
        1) не lock'ать тесты на конкретное значение ``skus`` (см. PR #9 review);
        2) после мерджа US-B2B-02 правка локализуется в одном месте;
        3) подклассы/моки могут переопределить без замены всего use-case.
        """
        return []

    async def __call__(
        self,
        product_id: UUID,
        current_user: AuthenticatedUserSchema,
    ) -> ProductResponseSchema:
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
            skus=skus,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )
