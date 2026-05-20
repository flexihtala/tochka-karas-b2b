from dishka import Provider, Scope, provide

from apps.categories.repositories import CategoryRepository
from apps.products.repositories import (
    CharacteristicValueRepository,
    ProductImageRepository,
    ProductRepository,
)
from apps.products.use_cases import CreateProductUseCase, GetProductUseCase


class ProductsProvider(Provider):
    product_repository = provide(ProductRepository, scope=Scope.REQUEST)
    image_repository = provide(ProductImageRepository, scope=Scope.REQUEST)
    characteristic_repository = provide(CharacteristicValueRepository, scope=Scope.REQUEST)
    category_repository = provide(CategoryRepository, scope=Scope.REQUEST)

    create_product_use_case = provide(CreateProductUseCase, scope=Scope.REQUEST)
    get_product_use_case = provide(GetProductUseCase, scope=Scope.REQUEST)
