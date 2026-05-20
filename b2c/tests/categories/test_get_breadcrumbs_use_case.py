from uuid import uuid4

import pytest

from apps.categories.errors import (
    AmbiguousBreadcrumbsParamsError,
    CategoryNotFoundError,
    MissingBreadcrumbsParamsError,
    OrphanCategoryNodeError,
)
from apps.categories.use_cases import GetBreadcrumbsUseCase
from tests.categories.fakes import FakeCategoryRepository, make_category


def _seed_three_level_tree(repo: FakeCategoryRepository):
    """Возвращает (root, mid, leaf) — типовое дерево из трёх уровней."""
    root = make_category(name='Электроника', slug='electronics')
    mid = make_category(name='Смартфоны', slug='phones', parent_id=root.id)
    leaf = make_category(name='Android', slug='android', parent_id=mid.id)
    repo.add(root)
    repo.add(mid)
    repo.add(leaf)
    return root, mid, leaf


@pytest.mark.anyio
async def test_breadcrumbs_return_path_from_root():
    """DoD test: возвращается путь от корня (level=0) до текущей категории."""
    repo = FakeCategoryRepository()
    root, mid, leaf = _seed_three_level_tree(repo)

    use_case = GetBreadcrumbsUseCase(category_repository=repo)
    result = await use_case(category_id=leaf.id, product_id=None)

    assert [n.slug for n in result.data] == ['electronics', 'phones', 'android']
    assert [n.level for n in result.data] == [0, 1, 2]
    assert [n.is_current for n in result.data] == [False, False, True]
    assert result.meta == {
        'resolved_via': 'category_id',
        'category_id': str(leaf.id),
    }


@pytest.mark.anyio
async def test_breadcrumbs_for_root_category_return_single_node():
    repo = FakeCategoryRepository()
    root, *_ = _seed_three_level_tree(repo)

    use_case = GetBreadcrumbsUseCase(category_repository=repo)
    result = await use_case(category_id=root.id, product_id=None)

    assert len(result.data) == 1
    assert result.data[0].slug == 'electronics'
    assert result.data[0].is_current is True
    assert result.data[0].level == 0


@pytest.mark.anyio
async def test_ambiguous_params_returns_400():
    """DoD test: одновременно category_id и product_id → 400 ambiguous_param."""
    repo = FakeCategoryRepository()
    use_case = GetBreadcrumbsUseCase(category_repository=repo)

    with pytest.raises(AmbiguousBreadcrumbsParamsError) as exc_info:
        await use_case(category_id=uuid4(), product_id=uuid4())

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == 'ambiguous_param'


@pytest.mark.anyio
async def test_missing_params_returns_400():
    repo = FakeCategoryRepository()
    use_case = GetBreadcrumbsUseCase(category_repository=repo)

    with pytest.raises(MissingBreadcrumbsParamsError) as exc_info:
        await use_case(category_id=None, product_id=None)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == 'missing_param'


@pytest.mark.anyio
async def test_breadcrumbs_for_unknown_category_returns_404():
    repo = FakeCategoryRepository()
    _seed_three_level_tree(repo)

    use_case = GetBreadcrumbsUseCase(category_repository=repo)

    with pytest.raises(CategoryNotFoundError):
        await use_case(category_id=uuid4(), product_id=None)


@pytest.mark.anyio
async def test_orphan_node_returns_422():
    """DoD test: цепочка предков обрывается на parent_id, на который никто не ссылается."""
    repo = FakeCategoryRepository()
    ghost_parent_id = uuid4()
    orphan = make_category(
        name='Orphan',
        slug='orphan',
        parent_id=ghost_parent_id,
    )
    repo.add(orphan)

    use_case = GetBreadcrumbsUseCase(category_repository=repo)

    with pytest.raises(OrphanCategoryNodeError) as exc_info:
        await use_case(category_id=orphan.id, product_id=None)

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == 'orphan_node'


@pytest.mark.anyio
async def test_breadcrumbs_by_product_id_resolves_via_marker():
    """product_id даёт тот же ответ, но resolved_via='product_id'."""
    repo = FakeCategoryRepository()
    root, mid, leaf = _seed_three_level_tree(repo)

    use_case = GetBreadcrumbsUseCase(category_repository=repo)
    result = await use_case(category_id=None, product_id=leaf.id)

    assert result.meta['resolved_via'] == 'product_id'
    assert result.meta['category_id'] == str(leaf.id)
    assert [n.slug for n in result.data] == ['electronics', 'phones', 'android']


@pytest.mark.anyio
async def test_breadcrumbs_detects_cycle_as_orphan():
    """Цикл в иерархии трактуется как сломанная структура (422)."""
    repo = FakeCategoryRepository()
    a_id = uuid4()
    b_id = uuid4()
    a = make_category(name='A', slug='a', parent_id=b_id, category_id=a_id)
    b = make_category(name='B', slug='b', parent_id=a_id, category_id=b_id)
    repo.add(a)
    repo.add(b)

    use_case = GetBreadcrumbsUseCase(category_repository=repo)

    with pytest.raises(OrphanCategoryNodeError):
        await use_case(category_id=a.id, product_id=None)
