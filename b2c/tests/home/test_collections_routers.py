from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.errors import setup_error_handlers
from apps.home.errors import CollectionNotFoundError
from apps.home.routers import router as home_router
from apps.home.schemas.response import (
    CollectionMetaResponseSchema,
    CollectionProductItemSchema,
    CollectionProductsResponseSchema,
)
from apps.home.use_cases import GetCollectionProductsUseCase, ListCollectionsUseCase


class StubListCollections:
    def __init__(self):
        self.calls = 0
        self.response: list[CollectionMetaResponseSchema] = []

    async def __call__(self) -> list[CollectionMetaResponseSchema]:
        self.calls += 1
        return self.response


class StubGetCollectionProducts:
    def __init__(self):
        self.calls: list[UUID] = []
        self.response: CollectionProductsResponseSchema | None = None
        self.error: Exception | None = None

    async def __call__(self, collection_id: UUID) -> CollectionProductsResponseSchema:
        self.calls.append(collection_id)
        if self.error:
            raise self.error
        return self.response or CollectionProductsResponseSchema(items=[], unavailable_ids=[])


class CollectionsRouteProvider(Provider):
    def __init__(self, list_stub: StubListCollections, products_stub: StubGetCollectionProducts):
        super().__init__()
        self.list_stub = list_stub
        self.products_stub = products_stub

    @provide(scope=Scope.REQUEST)
    def get_list_use_case(self) -> ListCollectionsUseCase:
        return self.list_stub

    @provide(scope=Scope.REQUEST)
    def get_products_use_case(self) -> GetCollectionProductsUseCase:
        return self.products_stub


def _make_app(list_stub: StubListCollections, products_stub: StubGetCollectionProducts) -> FastAPI:
    class _NoUser(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = None
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_NoUser)
    app.include_router(home_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        CollectionsRouteProvider(list_stub, products_stub),
    )
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs():
    return StubListCollections(), StubGetCollectionProducts()


def test_list_collections_returns_200_empty(stubs):
    list_stub, products_stub = stubs
    client = TestClient(_make_app(list_stub, products_stub))

    response = client.get('/api/v1/home/collections')

    assert response.status_code == 200
    assert response.json() == []
    assert list_stub.calls == 1


def test_list_collections_returns_metadata_only(stubs):
    list_stub, products_stub = stubs
    list_stub.response = [
        CollectionMetaResponseSchema(
            id=uuid4(),
            slug='top',
            title='Top',
            description=None,
            position=0,
        ),
        CollectionMetaResponseSchema(
            id=uuid4(),
            slug='sales',
            title='Sales',
            description='Discounted',
            position=1,
        ),
    ]
    client = TestClient(_make_app(list_stub, products_stub))

    response = client.get('/api/v1/home/collections')

    assert response.status_code == 200
    body = response.json()
    assert [c['slug'] for c in body] == ['top', 'sales']
    # Ответ — только метаданные.
    for c in body:
        assert 'items' not in c
        assert 'unavailable_ids' not in c


def test_get_collection_products_returns_items_and_unavailable(stubs):
    list_stub, products_stub = stubs
    available_id = uuid4()
    unavailable_id = uuid4()
    products_stub.response = CollectionProductsResponseSchema(
        items=[
            CollectionProductItemSchema(
                id=available_id,
                title='Apple',
                slug='apple',
                price=42.0,
                image_url='https://cdn.b2b/apple.png',
            )
        ],
        unavailable_ids=[unavailable_id],
    )
    collection_id = uuid4()
    client = TestClient(_make_app(list_stub, products_stub))

    response = client.get(f'/api/v1/home/collections/{collection_id}/products')

    assert response.status_code == 200
    body = response.json()
    assert body['items'][0]['id'] == str(available_id)
    assert body['unavailable_ids'] == [str(unavailable_id)]
    assert products_stub.calls == [collection_id]


def test_get_collection_products_unknown_returns_404(stubs):
    list_stub, products_stub = stubs
    products_stub.error = CollectionNotFoundError()
    client = TestClient(_make_app(list_stub, products_stub))

    response = client.get(f'/api/v1/home/collections/{uuid4()}/products')

    assert response.status_code == 404
    assert response.json() == {'code': 'NOT_FOUND', 'message': 'Подборка не найдена'}


def test_get_collection_products_empty_collection_returns_empty_lists(stubs):
    list_stub, products_stub = stubs
    products_stub.response = CollectionProductsResponseSchema(items=[], unavailable_ids=[])
    client = TestClient(_make_app(list_stub, products_stub))

    response = client.get(f'/api/v1/home/collections/{uuid4()}/products')

    assert response.status_code == 200
    assert response.json() == {'items': [], 'unavailable_ids': []}
