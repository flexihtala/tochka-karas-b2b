"""Dishka-провайдер для модуля public.

Содержит:
- PublicCatalogRepository (REQUEST-scope) — реальный репозиторий витрины.
- ListCatalogUseCase (REQUEST-scope) — use-case с прокинутым репозиторием.
"""

from dishka import Provider, Scope, provide

from apps.public.repositories import PublicCatalogRepository
from apps.public.use_cases import ListCatalogUseCase


class PublicProvider(Provider):
    catalog_repository = provide(PublicCatalogRepository, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def list_catalog_use_case(self, catalog_repository: PublicCatalogRepository) -> ListCatalogUseCase:
        return ListCatalogUseCase(repository=catalog_repository)
