from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.categories.errors import (
    AmbiguousBreadcrumbsParamsError,
    CategoryNotFoundError,
    MissingBreadcrumbsParamsError,
    OrphanCategoryNodeError,
)
from apps.categories.routers import router as categories_router
from apps.categories.schemas.response import (
    BreadcrumbsResponseSchema,
    CategoryBreadcrumbNodeSchema,
    CategoryResponseSchema,
    CategoryTreeNodeSchema,
    CategoryTreeResponseSchema,
)
from apps.categories.use_cases import GetBreadcrumbsUseCase, GetCategoryUseCase, GetTreeUseCase
from apps.errors import setup_error_handlers


def _make_category_response(category_id: UUID | None = None) -> CategoryResponseSchema:
    now = datetime.now(UTC)
    return CategoryResponseSchema(
        id=category_id or uuid4(),
        name='Электроника',
        slug='electronics',
        parent_id=None,
        ordering=0,
        created_at=now,
        updated_at=now,
    )


class StubGetTreeUseCase:
    def __init__(self):
        self.calls: int = 0
        self.error: Exception | None = None
        self.response = CategoryTreeResponseSchema(items=[])

    async def __call__(self) -> CategoryTreeResponseSchema:
        self.calls += 1
        if self.error:
            raise self.error
        return self.response


class StubGetCategoryUseCase:
    def __init__(self):
        self.calls: list[UUID] = []
        self.error: Exception | None = None
        self.response: CategoryResponseSchema | None = None

    async def __call__(self, category_id: UUID) -> CategoryResponseSchema:
        self.calls.append(category_id)
        if self.error:
            raise self.error
        return self.response or _make_category_response(category_id)


class StubGetBreadcrumbsUseCase:
    def __init__(self):
        self.calls: list[tuple[UUID | None, UUID | None]] = []
        self.error: Exception | None = None
        self.response: BreadcrumbsResponseSchema | None = None

    async def __call__(
        self,
        category_id: UUID | None,
        product_id: UUID | None,
    ) -> BreadcrumbsResponseSchema:
        self.calls.append((category_id, product_id))
        if self.error:
            raise self.error
        if self.response is not None:
            return self.response
        target = category_id if category_id is not None else product_id
        return BreadcrumbsResponseSchema(
            data=[
                CategoryBreadcrumbNodeSchema(
                    id=target or uuid4(),
                    name='Электроника',
                    slug='electronics',
                    level=0,
                    is_current=True,
                )
            ],
            meta={
                'resolved_via': 'category_id' if category_id is not None else 'product_id',
                'category_id': str(target),
            },
        )


class CategoriesRouteProvider(Provider):
    def __init__(
        self,
        tree_stub: StubGetTreeUseCase,
        category_stub: StubGetCategoryUseCase,
        breadcrumbs_stub: StubGetBreadcrumbsUseCase,
    ):
        super().__init__()
        self.tree_stub = tree_stub
        self.category_stub = category_stub
        self.breadcrumbs_stub = breadcrumbs_stub

    @provide(scope=Scope.REQUEST)
    def get_tree_use_case(self) -> GetTreeUseCase:
        return self.tree_stub

    @provide(scope=Scope.REQUEST)
    def get_category_use_case(self) -> GetCategoryUseCase:
        return self.category_stub

    @provide(scope=Scope.REQUEST)
    def get_breadcrumbs_use_case(self) -> GetBreadcrumbsUseCase:
        return self.breadcrumbs_stub


@pytest.fixture
def stubs():
    return (
        StubGetTreeUseCase(),
        StubGetCategoryUseCase(),
        StubGetBreadcrumbsUseCase(),
    )


@pytest.fixture
def client(stubs):
    tree_stub, category_stub, breadcrumbs_stub = stubs
    app = FastAPI()
    app.include_router(categories_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        CategoriesRouteProvider(tree_stub, category_stub, breadcrumbs_stub),
    )
    setup_dishka(container, app)
    return TestClient(app)


def test_get_tree_returns_200(client, stubs):
    tree_stub, _, _ = stubs
    root_id = uuid4()
    child_id = uuid4()
    tree_stub.response = CategoryTreeResponseSchema(
        items=[
            CategoryTreeNodeSchema(
                id=root_id,
                name='Электроника',
                slug='electronics',
                parent_id=None,
                ordering=0,
                children=[
                    CategoryTreeNodeSchema(
                        id=child_id,
                        name='Смартфоны',
                        slug='phones',
                        parent_id=root_id,
                        ordering=0,
                        children=[],
                    )
                ],
            )
        ]
    )

    response = client.get('/api/v1/catalog/categories/tree')

    assert response.status_code == 200
    body = response.json()
    # Per openapi spec: flat array of CategoryTreeNode at the root
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]['slug'] == 'electronics'
    assert body[0]['children'][0]['slug'] == 'phones'
    assert tree_stub.calls == 1


def test_get_tree_orphan_returns_422(client, stubs):
    tree_stub, _, _ = stubs
    tree_stub.error = OrphanCategoryNodeError()

    response = client.get('/api/v1/catalog/categories/tree')

    assert response.status_code == 422
    assert response.json() == {
        'code': 'orphan_node',
        'message': 'Иерархия категорий нарушена',
    }


def test_get_category_returns_200(client, stubs):
    _, category_stub, _ = stubs
    category_id = uuid4()

    response = client.get(f'/api/v1/catalog/categories/{category_id}')

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == str(category_id)
    assert body['slug'] == 'electronics'
    assert category_stub.calls == [category_id]


def test_get_category_returns_404_for_missing(client, stubs):
    _, category_stub, _ = stubs
    category_stub.error = CategoryNotFoundError()

    response = client.get(f'/api/v1/catalog/categories/{uuid4()}')

    assert response.status_code == 404
    assert response.json() == {'code': 'NOT_FOUND', 'message': 'Категория не найдена'}


def test_breadcrumbs_with_category_id_returns_200(client, stubs):
    _, _, breadcrumbs_stub = stubs
    category_id = uuid4()

    response = client.get(f'/api/v1/catalog/categories/breadcrumbs?category_id={category_id}')

    assert response.status_code == 200
    body = response.json()
    assert body['meta']['resolved_via'] == 'category_id'
    assert body['meta']['category_id'] == str(category_id)
    assert breadcrumbs_stub.calls == [(category_id, None)]


def test_breadcrumbs_with_product_id_returns_200(client, stubs):
    _, _, breadcrumbs_stub = stubs
    product_id = uuid4()

    response = client.get(f'/api/v1/catalog/categories/breadcrumbs?product_id={product_id}')

    assert response.status_code == 200
    body = response.json()
    assert body['meta']['resolved_via'] == 'product_id'
    assert breadcrumbs_stub.calls == [(None, product_id)]


def test_breadcrumbs_ambiguous_returns_400(client, stubs):
    _, _, breadcrumbs_stub = stubs
    breadcrumbs_stub.error = AmbiguousBreadcrumbsParamsError()

    response = client.get(f'/api/v1/catalog/categories/breadcrumbs?category_id={uuid4()}&product_id={uuid4()}')

    assert response.status_code == 400
    assert response.json()['code'] == 'ambiguous_param'


def test_breadcrumbs_missing_returns_400(client, stubs):
    _, _, breadcrumbs_stub = stubs
    breadcrumbs_stub.error = MissingBreadcrumbsParamsError()

    response = client.get('/api/v1/catalog/categories/breadcrumbs')

    assert response.status_code == 400
    assert response.json()['code'] == 'missing_param'


def test_breadcrumbs_orphan_returns_422(client, stubs):
    _, _, breadcrumbs_stub = stubs
    breadcrumbs_stub.error = OrphanCategoryNodeError()

    response = client.get(f'/api/v1/catalog/categories/breadcrumbs?category_id={uuid4()}')

    assert response.status_code == 422
    assert response.json()['code'] == 'orphan_node'


def test_breadcrumbs_unknown_category_returns_404(client, stubs):
    _, _, breadcrumbs_stub = stubs
    breadcrumbs_stub.error = CategoryNotFoundError()

    response = client.get(f'/api/v1/catalog/categories/breadcrumbs?category_id={uuid4()}')

    assert response.status_code == 404
    assert response.json()['code'] == 'NOT_FOUND'


def test_breadcrumbs_invalid_uuid_returns_400(client):
    response = client.get('/api/v1/catalog/categories/breadcrumbs?category_id=not-a-uuid')

    assert response.status_code == 400
