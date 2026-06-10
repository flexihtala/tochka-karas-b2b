from uuid import uuid4

import pytest

from apps.categories.errors import OrphanCategoryNodeError
from apps.categories.use_cases import GetFlatCategoriesUseCase, GetTreeUseCase
from tests.categories.fakes import FakeCategoryRepository, make_category


def _make_use_case(repo: FakeCategoryRepository) -> GetFlatCategoriesUseCase:
    return GetFlatCategoriesUseCase(get_tree_use_case=GetTreeUseCase(category_repository=repo))


@pytest.mark.anyio
async def test_flat_categories_returns_all_categories():
    """GET /catalog/categories возвращает все категории одним плоским списком."""
    repo = FakeCategoryRepository()
    electronics = make_category(name='Электроника', slug='electronics', ordering=0)
    clothes = make_category(name='Одежда', slug='clothes', ordering=1)
    phones = make_category(name='Смартфоны', slug='phones', parent_id=electronics.id)
    android = make_category(name='Android', slug='android', parent_id=phones.id)
    for category in (electronics, clothes, phones, android):
        repo.add(category)

    use_case = _make_use_case(repo)
    result = await use_case()

    assert len(result) == 4
    assert {item.id for item in result} == {electronics.id, clothes.id, phones.id, android.id}
    # DFS pre-order: родитель всегда раньше своих потомков.
    positions = {item.id: index for index, item in enumerate(result)}
    assert positions[electronics.id] < positions[phones.id] < positions[android.id]


@pytest.mark.anyio
async def test_flat_categories_have_correct_level_and_path():
    """level: корень = 0, +1 на уровень; path: имена от корня включая текущую."""
    repo = FakeCategoryRepository()
    root = make_category(name='Электроника', slug='electronics')
    child = make_category(name='Смартфоны', slug='phones', parent_id=root.id)
    grandchild = make_category(name='Android', slug='android', parent_id=child.id)
    for category in (root, child, grandchild):
        repo.add(category)

    use_case = _make_use_case(repo)
    result = await use_case()

    by_id = {item.id: item for item in result}

    assert by_id[root.id].level == 0
    assert by_id[root.id].path == ['Электроника']
    assert by_id[root.id].parent_id is None

    assert by_id[child.id].level == 1
    assert by_id[child.id].path == ['Электроника', 'Смартфоны']
    assert by_id[child.id].parent_id == root.id

    assert by_id[grandchild.id].level == 2
    assert by_id[grandchild.id].path == ['Электроника', 'Смартфоны', 'Android']
    assert by_id[grandchild.id].parent_id == child.id


@pytest.mark.anyio
async def test_flat_categories_empty_returns_empty_list():
    repo = FakeCategoryRepository()
    use_case = _make_use_case(repo)

    result = await use_case()

    assert result == []


@pytest.mark.anyio
async def test_flat_categories_with_orphan_node_raises_422_error():
    """Orphan-нода (parent_id на несуществующую категорию) → та же 422, что и в /tree."""
    repo = FakeCategoryRepository()
    repo.add(
        make_category(
            name='Orphan',
            slug='orphan',
            parent_id=uuid4(),  # parent не существует
        )
    )

    use_case = _make_use_case(repo)

    with pytest.raises(OrphanCategoryNodeError) as exc_info:
        await use_case()

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == 'orphan_node'
