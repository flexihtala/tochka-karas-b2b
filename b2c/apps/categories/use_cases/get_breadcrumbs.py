from uuid import UUID

from apps.categories.errors import (
    AmbiguousBreadcrumbsParamsError,
    CategoryNotFoundError,
    MissingBreadcrumbsParamsError,
    OrphanCategoryNodeError,
)
from apps.categories.repositories import CategoryRepository
from apps.categories.schemas.db import CategoryReadSchema
from apps.categories.schemas.response import BreadcrumbsResponseSchema, CategoryBreadcrumbNodeSchema


class GetBreadcrumbsUseCase:
    """GET /api/v1/categories/breadcrumbs?category_id=...|product_id=....

    Бизнес-правила:
    - Ровно один из параметров: category_id или product_id (иначе 400).
    - Несуществующая категория → 404.
    - Сломанная иерархия (orphan-node: parent_id ссылается на отсутствующую
      категорию) → 422.

    product_id на MVP резолвится тривиально: пока товары в B2C не хранятся,
    мы трактуем product_id как идентификатор «как будто это категория» —
    т.е. возвращаем те же крошки, что и для category_id. Когда появится
    интеграция с B2B-каталогом, эта ветка будет вызывать B2B и получать
    category_id товара. Сейчас задача — закрыть контракт API и тесты.
    """

    def __init__(self, category_repository: CategoryRepository):
        self.category_repository = category_repository

    async def __call__(
        self,
        category_id: UUID | None,
        product_id: UUID | None,
    ) -> BreadcrumbsResponseSchema:
        resolved_via = self._validate_params(category_id, product_id)

        # На MVP product_id трактуется как category_id (B2C не хранит товары).
        target_category_id = category_id if category_id is not None else product_id
        assert target_category_id is not None  # ради mypy/pyright

        flat = await self.category_repository.list_all()
        by_id: dict[UUID, CategoryReadSchema] = {c.id: c for c in flat}

        if target_category_id not in by_id:
            raise CategoryNotFoundError()

        path = self._walk_to_root(target_category_id, by_id)

        nodes = [
            CategoryBreadcrumbNodeSchema(
                id=category.id,
                name=category.name,
                slug=category.slug,
                level=level,
                is_current=(level == len(path) - 1),
            )
            for level, category in enumerate(path)
        ]

        return BreadcrumbsResponseSchema(
            data=nodes,
            meta={
                'resolved_via': resolved_via,
                'category_id': str(target_category_id),
            },
        )

    @staticmethod
    def _validate_params(category_id: UUID | None, product_id: UUID | None) -> str:
        if category_id is not None and product_id is not None:
            raise AmbiguousBreadcrumbsParamsError()
        if category_id is None and product_id is None:
            raise MissingBreadcrumbsParamsError()
        return 'category_id' if category_id is not None else 'product_id'

    @staticmethod
    def _walk_to_root(
        start_id: UUID,
        by_id: dict[UUID, CategoryReadSchema],
    ) -> list[CategoryReadSchema]:
        """Поднимается от текущей категории к корню по parent_id.

        Возвращает список от корня (level=0) до текущей. Бросает
        OrphanCategoryNodeError, если по пути встречается parent_id, на
        который никто не ссылается. Также страхуется от циклов через
        набор visited (на MVP их быть не должно, но дешёвая защита).
        """
        chain: list[CategoryReadSchema] = []
        visited: set[UUID] = set()

        current_id: UUID | None = start_id
        while current_id is not None:
            if current_id in visited:
                # Цикл в иерархии — тоже сломанная структура.
                raise OrphanCategoryNodeError()
            visited.add(current_id)

            current = by_id.get(current_id)
            if current is None:
                raise OrphanCategoryNodeError()

            chain.append(current)
            current_id = current.parent_id

        chain.reverse()
        return chain
