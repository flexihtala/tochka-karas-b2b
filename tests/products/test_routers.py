from dataclasses import dataclass
from uuid import uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.auth.dependencies import get_current_user
from apps.auth.enums import UserRole
from apps.auth.schemas.token import AuthenticatedUserSchema
from apps.errors import setup_error_handlers
from apps.products.repositories import (
    CategoryRepository,
    ProductCharacteristicRepository,
    ProductImageRepository,
    ProductRepository,
)
from apps.products.routers import router as products_router
from apps.products.schemas.category import CategoryReadSchema
from apps.products.use_cases import CreateProductUseCase
from tests.products.fakes import (
    FakeCategoryRepository,
    FakeProductCharacteristicRepository,
    FakeProductImageRepository,
    FakeProductRepository,
)


@dataclass
class ProductRouteFakes:
    categories: FakeCategoryRepository
    products: FakeProductRepository
    images: FakeProductImageRepository
    characteristics: FakeProductCharacteristicRepository


class ProductRouteProvider(Provider):
    def __init__(self, fakes: ProductRouteFakes):
        super().__init__()
        self.fakes = fakes

    @provide(scope=Scope.REQUEST)
    def get_product_repository(self) -> ProductRepository:
        return self.fakes.products

    @provide(scope=Scope.REQUEST)
    def get_product_image_repository(self) -> ProductImageRepository:
        return self.fakes.images

    @provide(scope=Scope.REQUEST)
    def get_product_characteristic_repository(self) -> ProductCharacteristicRepository:
        return self.fakes.characteristics

    @provide(scope=Scope.REQUEST)
    def get_category_repository(self) -> CategoryRepository:
        return self.fakes.categories

    create_product_use_case = provide(CreateProductUseCase, scope=Scope.REQUEST)


@pytest.fixture
def route_fakes() -> ProductRouteFakes:
    category = CategoryReadSchema(id=uuid4(), name='iOS')
    categories = FakeCategoryRepository()
    categories.add(category)
    return ProductRouteFakes(
        categories=categories,
        products=FakeProductRepository(),
        images=FakeProductImageRepository(),
        characteristics=FakeProductCharacteristicRepository(),
    )


@pytest.fixture
def client(route_fakes: ProductRouteFakes) -> TestClient:
    app = FastAPI()
    app.include_router(products_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), ProductRouteProvider(route_fakes))
    setup_dishka(container, app)
    seller_id = uuid4()
    app.state.seller_id = seller_id
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserSchema(
        id=seller_id,
        role=UserRole.SELLER,
    )
    return TestClient(app)


def product_payload(category_id: str) -> dict:
    return {
        'title': 'iPhone 15 Pro Max',
        'description': 'Флагманский смартфон Apple 2024 года с чипом A17 Pro',
        'category_id': category_id,
        'images': [{'url': '/s3/iphone15-front.jpg', 'ordering': 0}],
        'characteristics': [{'name': 'Бренд', 'value': 'Apple'}],
    }


def first_category_id(route_fakes: ProductRouteFakes) -> str:
    return str(next(iter(route_fakes.categories.categories)))


def test_create_product_route_returns_201_with_created_status(client: TestClient, route_fakes: ProductRouteFakes):
    response = client.post('/api/v1/products', json=product_payload(first_category_id(route_fakes)))

    assert response.status_code == 201
    body = response.json()
    assert body['status'] == 'CREATED'
    assert body['skus'] == []
    assert body['seller_id'] == str(client.app.state.seller_id)
    assert body['category_id'] == first_category_id(route_fakes)
    assert body['images'][0]['id']
    assert body['images'][0]['url'] == '/s3/iphone15-front.jpg'
    assert body['images'][0]['ordering'] == 0
    assert body['characteristics'][0]['id']
    assert body['characteristics'][0]['name'] == 'Бренд'
    assert body['created_at']
    assert body['updated_at']
    assert route_fakes.images.created_images[0].product_id == route_fakes.products.created_read_product.id
    assert (
        route_fakes.characteristics.created_characteristics[0].product_id
        == route_fakes.products.created_read_product.id
    )


def test_create_product_route_takes_seller_id_from_jwt(client: TestClient, route_fakes: ProductRouteFakes):
    payload = product_payload(first_category_id(route_fakes))
    payload['seller_id'] = str(uuid4())

    response = client.post('/api/v1/products', json=payload)

    assert response.status_code == 201
    assert route_fakes.products.created_product is not None
    assert route_fakes.products.created_product.seller_id == client.app.state.seller_id


def test_create_product_route_missing_images_returns_400(client: TestClient, route_fakes: ProductRouteFakes):
    payload = product_payload(first_category_id(route_fakes))
    payload.pop('images')

    response = client.post('/api/v1/products', json=payload)

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'At least one image is required'}


def test_create_product_route_missing_category_returns_400(client: TestClient, route_fakes: ProductRouteFakes):
    payload = product_payload(first_category_id(route_fakes))
    payload.pop('category_id')

    response = client.post('/api/v1/products', json=payload)

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'category_id is required'}


def test_create_product_route_missing_title_returns_400(client: TestClient, route_fakes: ProductRouteFakes):
    payload = product_payload(first_category_id(route_fakes))
    payload.pop('title')

    response = client.post('/api/v1/products', json=payload)

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'title is required'}


def test_create_product_route_invalid_category_id_returns_400(client: TestClient, route_fakes: ProductRouteFakes):
    response = client.post('/api/v1/products', json=product_payload(str(uuid4())))

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Category not found'}


def test_product_create_openapi_marks_title_and_category_required(client: TestClient):
    response = client.get('/openapi.json')

    assert response.status_code == 200
    required = response.json()['components']['schemas']['ProductCreateRequestSchema']['required']
    assert 'title' in required
    assert 'category_id' in required
