from apps.skus.models import SKUCharacteristic
from apps.skus.schemas import (
    SKUCharacteristicCreateSchema,
    SKUCharacteristicReadSchema,
    SKUCharacteristicUpdateSchema,
)
from db import DBCrudRepository


class SKUCharacteristicRepository(
    DBCrudRepository[
        SKUCharacteristic,
        SKUCharacteristicCreateSchema,
        SKUCharacteristicReadSchema,
        SKUCharacteristicUpdateSchema,
    ]
):
    pass
