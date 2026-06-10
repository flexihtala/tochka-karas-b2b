from dishka import Provider, Scope, provide

from apps.categories.repositories import CategoryRepository
from apps.categories.use_cases import (
    GetBreadcrumbsUseCase,
    GetCategoryUseCase,
    GetFlatCategoriesUseCase,
    GetTreeUseCase,
)


class CategoriesProvider(Provider):
    category_repository = provide(CategoryRepository, scope=Scope.REQUEST)
    get_tree_use_case = provide(GetTreeUseCase, scope=Scope.REQUEST)
    get_flat_categories_use_case = provide(GetFlatCategoriesUseCase, scope=Scope.REQUEST)
    get_category_use_case = provide(GetCategoryUseCase, scope=Scope.REQUEST)
    get_breadcrumbs_use_case = provide(GetBreadcrumbsUseCase, scope=Scope.REQUEST)
