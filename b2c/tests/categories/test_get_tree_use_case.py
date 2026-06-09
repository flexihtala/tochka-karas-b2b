from uuid import uuid4

import pytest

from apps.categories.errors import OrphanCategoryNodeError
from apps.categories.use_cases import GetTreeUseCase
from tests.categories.fakes import FakeCategoryRepository, make_category


@pytest.mark.anyio
async def test_category_tree_returns_nested_structure():
    """DoD test: GET /tree собирает корректную вложенную иерархию из плоского списка."""
    repo = FakeCategoryRepository()

    electronics = make_category(name='Электроника', slug='electronics', ordering=0)
    clothes = make_category(name='Одежда', slug='clothes', ordering=1)
    phones = make_category(
        name='Смартфоны',
        slug='phones',
        parent_id=electronics.id,
        ordering=0,
    )
    laptops = make_category(
        name='Ноутбуки',
        slug='laptops',
        parent_id=electronics.id,
        ordering=1,
    )
    android = make_category(name='Android', slug='android', parent_id=phones.id)

    for category in (electronics, clothes, phones, laptops, android):
        repo.add(category)

    use_case = GetTreeUseCase(category_repository=repo)
    result = await use_case()

    assert [node.slug for node in result.items] == ['electronics', 'clothes']

    electronics_node = result.items[0]
    assert electronics_node.parent_id is None
    assert [c.slug for c in electronics_node.children] == ['phones', 'laptops']

    phones_node = electronics_node.children[0]
    assert phones_node.parent_id == electronics.id
    assert [c.slug for c in phones_node.children] == ['android']
    assert phones_node.children[0].children == []

    clothes_node = result.items[1]
    assert clothes_node.children == []


@pytest.mark.anyio
async def test_empty_tree_returns_empty_items_list():
    repo = FakeCategoryRepository()
    use_case = GetTreeUseCase(category_repository=repo)

    result = await use_case()

    assert result.items == []


@pytest.mark.anyio
async def test_tree_with_orphan_node_raises_422_error():
    """В дереве есть категория с parent_id, на который никто не ссылается → 422."""
    repo = FakeCategoryRepository()
    repo.add(
        make_category(
            name='Orphan',
            slug='orphan',
            parent_id=uuid4(),  # parent не существует
        )
    )

    use_case = GetTreeUseCase(category_repository=repo)

    with pytest.raises(OrphanCategoryNodeError):
        await use_case()


@pytest.mark.anyio
async def test_tree_children_sorted_by_ordering_then_name():
    repo = FakeCategoryRepository()
    root = make_category(name='Root', slug='root')
    repo.add(root)
    repo.add(make_category(name='B', slug='b', parent_id=root.id, ordering=2))
    repo.add(make_category(name='A', slug='a', parent_id=root.id, ordering=1))
    repo.add(make_category(name='C', slug='c', parent_id=root.id, ordering=1))

    use_case = GetTreeUseCase(category_repository=repo)
    result = await use_case()

    children_slugs = [c.slug for c in result.items[0].children]
    # сначала ordering=1 (A,C — упорядочены по name), потом ordering=2 (B)
    assert children_slugs == ['a', 'c', 'b']
