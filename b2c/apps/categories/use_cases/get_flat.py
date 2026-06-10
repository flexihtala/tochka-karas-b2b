from apps.categories.schemas.response import CategoryRefSchema, CategoryTreeNodeSchema
from apps.categories.use_cases.get_tree import GetTreeUseCase


class GetFlatCategoriesUseCase:
    """GET /api/v1/catalog/categories — плоский список всех категорий (CategoryRef).

    Переиспользует сборку дерева из GetTreeUseCase: level и path вычисляются
    тем же кодом, после чего дерево разворачивается DFS-обходом (pre-order)
    в плоский список. Orphan-нода даёт ту же 422 (OrphanCategoryNodeError),
    что и /tree — контракт по ошибкам у обоих маршрутов одинаковый.
    """

    def __init__(self, get_tree_use_case: GetTreeUseCase):
        self.get_tree_use_case = get_tree_use_case

    async def __call__(self) -> list[CategoryRefSchema]:
        tree = await self.get_tree_use_case()
        return self._flatten(tree.items)

    def _flatten(self, nodes: list[CategoryTreeNodeSchema]) -> list[CategoryRefSchema]:
        flat: list[CategoryRefSchema] = []
        for node in nodes:
            flat.append(
                CategoryRefSchema(
                    id=node.id,
                    name=node.name,
                    parent_id=node.parent_id,
                    level=node.level,
                    path=node.path,
                )
            )
            flat.extend(self._flatten(node.children))
        return flat
