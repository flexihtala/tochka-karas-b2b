from apps.products.models import Product
from apps.products.schemas.product import ProductCreateSchema, ProductReadSchema, ProductUpdateSchema
from db import DBCrudRepository


class ProductRepository(DBCrudRepository[Product, ProductCreateSchema, ProductReadSchema, ProductUpdateSchema]):
    pass
