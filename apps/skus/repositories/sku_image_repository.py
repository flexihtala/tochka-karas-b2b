from apps.skus.models import SKUImage
from apps.skus.schemas import SKUImageCreateSchema, SKUImageReadSchema, SKUImageUpdateSchema
from db import DBCrudRepository


class SKUImageRepository(DBCrudRepository[SKUImage, SKUImageCreateSchema, SKUImageReadSchema, SKUImageUpdateSchema]):
    pass
