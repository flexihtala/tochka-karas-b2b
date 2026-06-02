"""Dishka-провайдер для модуля public.

Содержит:
- PublicCatalogRepository (REQUEST-scope) — реальный репозиторий витрины.
- 5 use-case'ов витрины (REQUEST-scope) с прокинутым репозиторием.
"""

from dishka import Provider, Scope, provide

from apps.public.repositories import PublicCatalogRepository
from apps.public.use_cases import (
    BatchProductsUseCase,
    GetPublicProductUseCase,
    GetPublicSKUUseCase,
    GetSimilarProductsUseCase,
    ListCatalogUseCase,
)


class PublicProvider(Provider):
    catalog_repository = provide(PublicCatalogRepository, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def list_catalog_use_case(self, catalog_repository: PublicCatalogRepository) -> ListCatalogUseCase:
        return ListCatalogUseCase(repository=catalog_repository)

    @provide(scope=Scope.REQUEST)
    def batch_products_use_case(self, catalog_repository: PublicCatalogRepository) -> BatchProductsUseCase:
        return BatchProductsUseCase(repository=catalog_repository)

    @provide(scope=Scope.REQUEST)
    def get_product_use_case(self, catalog_repository: PublicCatalogRepository) -> GetPublicProductUseCase:
        return GetPublicProductUseCase(repository=catalog_repository)

    @provide(scope=Scope.REQUEST)
    def get_similar_use_case(self, catalog_repository: PublicCatalogRepository) -> GetSimilarProductsUseCase:
        return GetSimilarProductsUseCase(repository=catalog_repository)

    @provide(scope=Scope.REQUEST)
    def get_sku_use_case(self, catalog_repository: PublicCatalogRepository) -> GetPublicSKUUseCase:
        return GetPublicSKUUseCase(repository=catalog_repository)
