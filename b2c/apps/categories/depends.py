from dishka import Provider, Scope, provide

from apps.categories.repositories import CategoryRepository
from apps.categories.use_cases import (
    GetBreadcrumbsUseCase,
    GetCategoryUseCase,
    GetTreeUseCase,
)


class CategoriesProvider(Provider):
    category_repository = provide(CategoryRepository, scope=Scope.REQUEST)
    get_tree_use_case = provide(GetTreeUseCase, scope=Scope.REQUEST)
    get_category_use_case = provide(GetCategoryUseCase, scope=Scope.REQUEST)
    get_breadcrumbs_use_case = provide(GetBreadcrumbsUseCase, scope=Scope.REQUEST)
