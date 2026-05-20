from apps.products.enums import ProductStatus
from apps.products.repositories import ProductImageRepository, ProductRepository
from apps.products.schemas.response import (
    ProductImageResponseSchema,
    ProductListItemResponseSchema,
    ProductPaginatedResponseSchema,
)
from shared.auth_lib import AuthenticatedUserSchema


class ListSellerProductsUseCase:
    """B2B-11: список товаров продавца.

    Бизнес-правила:
    - seller_id ВСЕГДА берётся из JWT-клеймов (current_user.id). Любой query-параметр
      `seller_id` игнорируется на уровне роутера (FastAPI его не объявляет) и здесь —
      это защита от IDOR.
    - По умолчанию возвращаются только не удалённые товары (`deleted=false`).
      `include_deleted=true` снимает фильтр.
    - Поиск по title — ILIKE без учёта регистра.
    - Агрегаты `skus_count` и `total_active_quantity` — заглушка `0` до US-B2B-02
      (модель SKU отсутствует в main). ADR в PR: после появления SKU считать
      `Count` / `Sum(active_quantity)` через correlated subquery в одном `SELECT`
      (без N+1) — добавим в US-B2B-02.
    """

    def __init__(
        self,
        product_repository: ProductRepository,
        image_repository: ProductImageRepository,
    ):
        self.product_repository = product_repository
        self.image_repository = image_repository

    async def __call__(
        self,
        *,
        current_user: AuthenticatedUserSchema,
        limit: int,
        offset: int,
        status: ProductStatus | None = None,
        include_deleted: bool = False,
        search: str | None = None,
    ) -> ProductPaginatedResponseSchema:
        products, total_count = await self.product_repository.list_for_seller(
            seller_id=current_user.id,
            limit=limit,
            offset=offset,
            status=status,
            include_deleted=include_deleted,
            search=search,
        )

        items: list[ProductListItemResponseSchema] = []
        for product in products:
            images = await self.image_repository.list_by_product(product.id)
            items.append(
                ProductListItemResponseSchema(
                    id=product.id,
                    seller_id=product.seller_id,
                    category_id=product.category_id,
                    title=product.title,
                    slug=product.slug,
                    status=product.status,
                    deleted=product.deleted,
                    images=[
                        ProductImageResponseSchema(id=image.id, url=image.url, ordering=image.ordering)
                        for image in images
                    ],
                    skus_count=0,
                    total_active_quantity=0,
                    created_at=product.created_at,
                    updated_at=product.updated_at,
                )
            )

        return ProductPaginatedResponseSchema(
            items=items,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )
