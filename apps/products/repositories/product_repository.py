from apps.products.models import Product, ProductCharacteristic, ProductImage
from apps.products.schemas.product import (
    ProductCharacteristicCreateSchema,
    ProductCharacteristicReadSchema,
    ProductCharacteristicUpdateSchema,
    ProductCreateSchema,
    ProductImageCreateSchema,
    ProductImageReadSchema,
    ProductImageUpdateSchema,
    ProductReadSchema,
    ProductUpdateSchema,
)
from db import DBCrudRepository


class ProductRepository(DBCrudRepository[Product, ProductCreateSchema, ProductReadSchema, ProductUpdateSchema]):
    pass


class ProductImageRepository(
    DBCrudRepository[ProductImage, ProductImageCreateSchema, ProductImageReadSchema, ProductImageUpdateSchema]
):
    pass


class ProductCharacteristicRepository(
    DBCrudRepository[
        ProductCharacteristic,
        ProductCharacteristicCreateSchema,
        ProductCharacteristicReadSchema,
        ProductCharacteristicUpdateSchema,
    ]
):
    pass
