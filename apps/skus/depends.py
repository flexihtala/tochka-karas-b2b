from dishka import Provider, Scope, provide

from apps.skus.repositories import (
    ModerationRepository,
    SKUCharacteristicRepository,
    SKUImageRepository,
    SKURepository,
)
from apps.skus.use_cases import CreateSKUUseCase, EditSKUUseCase


class SkusProvider(Provider):
    sku_repository = provide(SKURepository, scope=Scope.REQUEST)
    sku_image_repository = provide(SKUImageRepository, scope=Scope.REQUEST)
    sku_characteristic_repository = provide(SKUCharacteristicRepository, scope=Scope.REQUEST)
    moderation_repository = provide(ModerationRepository, scope=Scope.REQUEST)

    create_sku_use_case = provide(CreateSKUUseCase, scope=Scope.REQUEST)
    edit_sku_use_case = provide(EditSKUUseCase, scope=Scope.REQUEST)


provider = SkusProvider()
