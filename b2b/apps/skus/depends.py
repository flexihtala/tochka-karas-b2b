from dishka import Provider, Scope, provide

from apps.skus.repositories import (
    SKUCharacteristicValueRepository,
    SKUImageRepository,
    SKURepository,
)
from apps.skus.use_cases import CreateSKUUseCase, DeleteSKUUseCase


class SKUsProvider(Provider):
    sku_repository = provide(SKURepository, scope=Scope.REQUEST)
    sku_image_repository = provide(SKUImageRepository, scope=Scope.REQUEST)
    sku_characteristic_repository = provide(SKUCharacteristicValueRepository, scope=Scope.REQUEST)

    create_sku_use_case = provide(CreateSKUUseCase, scope=Scope.REQUEST)
    delete_sku_use_case = provide(DeleteSKUUseCase, scope=Scope.REQUEST)
