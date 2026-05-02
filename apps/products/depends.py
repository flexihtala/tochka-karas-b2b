from dishka import Provider, Scope, provide

from apps.products.repositories import (
    CategoryRepository,
    ProductCharacteristicRepository,
    ProductImageRepository,
    ProductRepository,
)
from apps.products.use_cases import CreateProductUseCase


class ProductsProvider(Provider):
    product_repository = provide(ProductRepository, scope=Scope.REQUEST)
    product_image_repository = provide(ProductImageRepository, scope=Scope.REQUEST)
    product_characteristic_repository = provide(ProductCharacteristicRepository, scope=Scope.REQUEST)
    category_repository = provide(CategoryRepository, scope=Scope.REQUEST)

    create_product_use_case = provide(CreateProductUseCase, scope=Scope.REQUEST)
