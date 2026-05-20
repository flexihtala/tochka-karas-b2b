from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from apps.home.errors import CollectionNotFoundError
from apps.home.schemas.db import CollectionItemReadSchema, CollectionReadSchema
from apps.home.services import B2BProductSchema
from apps.home.use_cases import GetCollectionProductsUseCase, ListCollectionsUseCase
from tests.home.fakes import (
    FakeB2BProductsClient,
    FakeCollectionItemRepository,
    FakeCollectionRepository,
)


def make_collection(
    *,
    collection_id: UUID | None = None,
    slug: str = 'promo',
    title: str = 'Promo',
    description: str | None = 'Promo collection',
    position: int = 0,
    is_active: bool = True,
) -> CollectionReadSchema:
    now = datetime.now(UTC)
    return CollectionReadSchema(
        id=collection_id or uuid4(),
        slug=slug,
        title=title,
        description=description,
        position=position,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def make_item(collection_id: UUID, product_id: UUID, ordering: int) -> CollectionItemReadSchema:
    now = datetime.now(UTC)
    return CollectionItemReadSchema(
        id=uuid4(),
        collection_id=collection_id,
        product_id=product_id,
        ordering=ordering,
        created_at=now,
        updated_at=now,
    )


def make_b2b_product(product_id: UUID, title: str) -> B2BProductSchema:
    return B2BProductSchema(
        id=product_id,
        title=title,
        slug=title.lower().replace(' ', '-'),
        price=100.0,
        image_url=f'https://cdn.b2b.example.com/{title}.png',
    )


@pytest.mark.anyio
async def test_collections_list_returns_metadata_without_products():
    """GET /home/collections — только метаданные, без обращения к b2b или collection_items."""
    repo = FakeCollectionRepository()
    repo.add(make_collection(slug='top', title='Top', position=0))
    repo.add(make_collection(slug='sales', title='Sales', position=2))
    repo.add(make_collection(slug='hidden', title='Hidden', position=1, is_active=False))

    use_case = ListCollectionsUseCase(collection_repository=repo)
    result = await use_case()

    assert [c.slug for c in result] == ['top', 'sales']
    # Тип возврата — CollectionMetaResponseSchema, в нём нет items / unavailable_ids.
    for c in result:
        assert not hasattr(c, 'items')
        assert not hasattr(c, 'unavailable_ids')


@pytest.mark.anyio
async def test_collection_products_enriched_from_b2b():
    """GET /home/collections/{id}/products — порядок ordering сохранён, поля карточки взяты из b2b."""
    collection = make_collection()
    pid1 = uuid4()
    pid2 = uuid4()
    pid3 = uuid4()
    item_repo = FakeCollectionItemRepository()
    item_repo.add(make_item(collection.id, pid1, ordering=2))
    item_repo.add(make_item(collection.id, pid2, ordering=0))
    item_repo.add(make_item(collection.id, pid3, ordering=1))

    b2b = FakeB2BProductsClient()
    b2b.add_available(make_b2b_product(pid1, 'Apple'))
    b2b.add_available(make_b2b_product(pid2, 'Banana'))
    b2b.add_available(make_b2b_product(pid3, 'Cherry'))

    collection_repo = FakeCollectionRepository()
    collection_repo.add(collection)
    use_case = GetCollectionProductsUseCase(
        collection_repository=collection_repo,
        collection_item_repository=item_repo,
        b2b_products_client=b2b,
    )

    result = await use_case(collection.id)

    assert result.unavailable_ids == []
    assert [it.id for it in result.items] == [pid2, pid3, pid1]
    assert result.items[0].title == 'Banana'
    assert result.items[0].slug == 'banana'
    assert result.items[0].price == 100.0
    assert result.items[0].image_url is not None
    # Запрос ушёл одним батчем с правильным порядком.
    assert b2b.batches_called == [[pid2, pid3, pid1]]


@pytest.mark.anyio
async def test_unavailable_products_in_unavailable_ids():
    """Если b2b не вернул товар (BLOCKED/удалён) — его uuid в unavailable_ids, items без него."""
    collection = make_collection()
    available_id = uuid4()
    blocked_id = uuid4()
    deleted_id = uuid4()

    item_repo = FakeCollectionItemRepository()
    item_repo.add(make_item(collection.id, available_id, ordering=0))
    item_repo.add(make_item(collection.id, blocked_id, ordering=1))
    item_repo.add(make_item(collection.id, deleted_id, ordering=2))

    b2b = FakeB2BProductsClient()
    b2b.add_available(make_b2b_product(available_id, 'Ok Product'))
    # blocked_id и deleted_id b2b не возвращает.

    collection_repo = FakeCollectionRepository()
    collection_repo.add(collection)
    use_case = GetCollectionProductsUseCase(
        collection_repository=collection_repo,
        collection_item_repository=item_repo,
        b2b_products_client=b2b,
    )

    result = await use_case(collection.id)

    assert [it.id for it in result.items] == [available_id]
    assert set(result.unavailable_ids) == {blocked_id, deleted_id}


@pytest.mark.anyio
async def test_unknown_collection_returns_404():
    """GET /home/collections/{id}/products для несуществующей подборки → CollectionNotFoundError (404)."""
    collection_repo = FakeCollectionRepository()
    item_repo = FakeCollectionItemRepository()
    b2b = FakeB2BProductsClient()
    use_case = GetCollectionProductsUseCase(
        collection_repository=collection_repo,
        collection_item_repository=item_repo,
        b2b_products_client=b2b,
    )

    with pytest.raises(CollectionNotFoundError) as exc_info:
        await use_case(uuid4())

    assert exc_info.value.status_code == 404
    # B2B не должен был дёргаться, если коллекции нет.
    assert b2b.batches_called == []


@pytest.mark.anyio
async def test_empty_collection_returns_200_with_empty_lists():
    """Подборка без товаров → пустые items и unavailable_ids; b2b не зовём."""
    collection = make_collection()
    collection_repo = FakeCollectionRepository()
    collection_repo.add(collection)
    item_repo = FakeCollectionItemRepository()
    b2b = FakeB2BProductsClient()

    use_case = GetCollectionProductsUseCase(
        collection_repository=collection_repo,
        collection_item_repository=item_repo,
        b2b_products_client=b2b,
    )

    result = await use_case(collection.id)

    assert result.items == []
    assert result.unavailable_ids == []
    assert b2b.batches_called == []
