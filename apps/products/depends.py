from dishka import Provider, Scope, provide

from apps.products.repositories import CategoryRepository, ProductRepository
from apps.products.use_cases import CreateProductUseCase


class ProductsProvider(Provider):
    product_repository = provide(ProductRepository, scope=Scope.REQUEST)
    category_repository = provide(CategoryRepository, scope=Scope.REQUEST)

    create_product_use_case = provide(CreateProductUseCase, scope=Scope.REQUEST)
