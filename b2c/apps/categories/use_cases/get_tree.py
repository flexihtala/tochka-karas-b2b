from collections import defaultdict
from uuid import UUID

from apps.categories.errors import OrphanCategoryNodeError
from apps.categories.repositories import CategoryRepository
from apps.categories.schemas.db import CategoryReadSchema
from apps.categories.schemas.response import CategoryTreeNodeSchema, CategoryTreeResponseSchema


class GetTreeUseCase:
    """GET /api/v1/categories/tree — собирает вложенное дерево категорий.

    Алгоритм:
    1. Берём все категории одним запросом.
    2. Группируем по parent_id.
    3. Строим вложенное дерево, начиная с корней (parent_id IS NULL).
    4. Если в БД есть категория с parent_id, на который никто не ссылается
       (orphan), бросаем 422 — иначе клиент получит обрезанное дерево
       без явного сигнала об ошибке.

    Попутно каждому узлу проставляются level (корень = 0, +1 на уровень
    вложенности) и path (имена категорий от корня до текущей включительно).
    """

    def __init__(self, category_repository: CategoryRepository):
        self.category_repository = category_repository

    async def __call__(self) -> CategoryTreeResponseSchema:
        flat = await self.category_repository.list_all()
        roots = self._build_tree(flat)
        return CategoryTreeResponseSchema(items=roots)

    def _build_tree(self, flat: list[CategoryReadSchema]) -> list[CategoryTreeNodeSchema]:
        by_parent: dict[UUID | None, list[CategoryReadSchema]] = defaultdict(list)
        all_ids: set[UUID] = set()
        for category in flat:
            by_parent[category.parent_id].append(category)
            all_ids.add(category.id)

        # Проверка на orphan-ноды: parent_id ссылается на несуществующую категорию.
        for category in flat:
            if category.parent_id is not None and category.parent_id not in all_ids:
                raise OrphanCategoryNodeError()

        def build_node(node: CategoryReadSchema, level: int, parent_path: list[str]) -> CategoryTreeNodeSchema:
            path = [*parent_path, node.name]
            return CategoryTreeNodeSchema(
                id=node.id,
                name=node.name,
                slug=node.slug,
                parent_id=node.parent_id,
                ordering=node.ordering,
                level=level,
                path=path,
                children=build_subtree(node.id, level + 1, path),
            )

        def build_subtree(
            parent_id: UUID | None,
            level: int,
            parent_path: list[str],
        ) -> list[CategoryTreeNodeSchema]:
            return [
                build_node(node, level, parent_path)
                for node in sorted(by_parent.get(parent_id, []), key=lambda c: (c.ordering, c.name))
            ]

        return build_subtree(None, 0, [])
