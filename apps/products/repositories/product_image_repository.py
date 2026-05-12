from apps.products.models import ProductImage
from apps.products.schemas.product import ProductImageCreateSchema, ProductImageReadSchema, ProductImageUpdateSchema
from db import DBCrudRepository


class ProductImageRepository(
    DBCrudRepository[ProductImage, ProductImageCreateSchema, ProductImageReadSchema, ProductImageUpdateSchema]
):
    pass
