"""Мапперы сырых снимков (ORM-модели или фейки) в public-response схемы.

Работают и с реальными моделями (Product/SKU + подгруженные связи), и с фейками
из tests/public — за счёт duck typing (одинаковый набор атрибутов).
"""

from apps.public.schemas.response import (
    CharacteristicPublicResponseSchema,
    ProductImagePublicResponseSchema,
    ProductPublicResponseSchema,
    ProductPublicShortResponseSchema,
    SKUImagePublicResponseSchema,
    SKUPublicResponseSchema,
)


def to_sku_response(sku) -> SKUPublicResponseSchema:
    return SKUPublicResponseSchema(
        id=sku.id,
        product_id=sku.product_id,
        name=sku.name,
        price=sku.price,
        discount=sku.discount,
        stock_quantity=sku.stock_quantity,
        active_quantity=sku.active_quantity,
        article=sku.article,
        images=[SKUImagePublicResponseSchema(id=img.id, url=img.url, ordering=img.ordering) for img in sku.images],
        characteristics=[
            CharacteristicPublicResponseSchema(id=ch.id, name=ch.name, value=ch.value) for ch in sku.characteristics
        ],
    )


def to_full_response(product) -> ProductPublicResponseSchema:
    return ProductPublicResponseSchema(
        id=product.id,
        seller_id=product.seller_id,
        category_id=product.category_id,
        title=product.title,
        slug=product.slug,
        description=product.description,
        status=product.status,
        images=[
            ProductImagePublicResponseSchema(id=image.id, url=image.url, ordering=image.ordering)
            for image in product.images
        ],
        characteristics=[
            CharacteristicPublicResponseSchema(id=ch.id, name=ch.name, value=ch.value) for ch in product.characteristics
        ],
        skus=[to_sku_response(sku) for sku in product.skus],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def to_short_response(product) -> ProductPublicShortResponseSchema:
    """Короткая карточка. min_price / cover_image берутся с атрибутов снимка,
    которые проставляет репозиторий (или фейк) при выборке.
    """
    return ProductPublicShortResponseSchema(
        id=product.id,
        title=product.title,
        slug=product.slug,
        status=product.status,
        category_id=product.category_id,
        min_price=product.min_price,
        cover_image=product.cover_image,
        created_at=product.created_at,
    )
