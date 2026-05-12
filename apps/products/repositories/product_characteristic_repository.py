from apps.products.models import ProductCharacteristic
from apps.products.schemas.product import (
    ProductCharacteristicCreateSchema,
    ProductCharacteristicReadSchema,
    ProductCharacteristicUpdateSchema,
)
from db import DBCrudRepository


class ProductCharacteristicRepository(
    DBCrudRepository[
        ProductCharacteristic,
        ProductCharacteristicCreateSchema,
        ProductCharacteristicReadSchema,
        ProductCharacteristicUpdateSchema,
    ]
):
    pass
