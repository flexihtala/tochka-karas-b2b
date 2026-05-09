from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.auth.dependencies import get_current_user
from apps.auth.enums import UserRole
from apps.auth.schemas import AuthenticatedUserSchema
from apps.errors import setup_error_handlers
from apps.products.enums import ProductStatus
from apps.products.repositories import ProductRepository
from apps.products.schemas import ProductReadSchema, ProductUpdateSchema
from apps.skus.repositories import (
    ModerationRepository,
    SKUCharacteristicRepository,
    SKUImageRepository,
    SKURepository,
)
from apps.skus.routers import router as skus_router
from apps.skus.schemas import SKUCharacteristicReadSchema, SKUImageReadSchema, SKUReadSchema, SKUUpdateSchema
from apps.skus.schemas.moderation import ProductModerationEventSchema
from apps.skus.use_cases import CreateSKUUseCase, EditSKUUseCase


class FakeProductRepository:
    def __init__(self, product: ProductReadSchema):
        self.product = product

    async def get_or_none(self, id_: UUID) -> ProductReadSchema | None:
        return self.product if self.product.id == id_ else None

    async def update(self, data: ProductUpdateSchema) -> ProductReadSchema:
        update_values = data.model_dump(exclude_unset=True, exclude={'id'})
        self.product = self.product.model_copy(update=update_values)
        return self.product


class FakeSKURepository:
    def __init__(self, existing: list[SKUReadSchema] | None = None):
        self.created_skus: list[SKUReadSchema] = []
        self.skus: dict[UUID, SKUReadSchema] = {}
        self.updated_skus: list[SKUUpdateSchema] = []
        if existing:
            for sku in existing:
                self.skus[sku.id] = sku

    async def count_by_product_id(self, product_id: UUID) -> int:
        return 0

    async def create(self, data) -> SKUReadSchema:
        now = datetime.now(UTC)
        sku = SKUReadSchema(
            id=uuid4(),
            product_id=data.product_id,
            name=data.name,
            price=data.price,
            stock_quantity=data.stock_quantity,
            article=data.article,
            cost_price=data.cost_price,
            discount=data.discount,
            created_at=now,
            updated_at=now,
        )
        self.created_skus.append(sku)
        self.skus[sku.id] = sku
        return sku

    async def get_or_none(self, id_: UUID) -> SKUReadSchema | None:
        return self.skus.get(id_)

    async def update(self, data: SKUUpdateSchema) -> SKUReadSchema | None:
        self.updated_skus.append(data)
        sku = self.skus.get(data.id)
        if sku is None:
            return None
        update_values = data.model_dump(exclude_unset=True, exclude={'id'})
        updated = sku.model_copy(update=update_values)
        self.skus[data.id] = updated
        return updated


class FakeSKUImageRepository:
    def __init__(self):
        self.deleted_for: list[UUID] = []

    async def create(self, data) -> SKUImageReadSchema:
        return SKUImageReadSchema(
            id=uuid4(),
            sku_id=data.sku_id,
            url=data.url,
            ordering=data.ordering,
        )

    async def delete_by_sku_id(self, sku_id: UUID) -> None:
        self.deleted_for.append(sku_id)


class FakeSKUCharacteristicRepository:
    def __init__(self):
        self.deleted_for: list[UUID] = []

    async def create(self, data) -> SKUCharacteristicReadSchema:
        return SKUCharacteristicReadSchema(
            id=uuid4(),
            sku_id=data.sku_id,
            name=data.name,
            value=data.value,
        )

    async def delete_by_sku_id(self, sku_id: UUID) -> None:
        self.deleted_for.append(sku_id)


class FakeModerationRepository:
    def __init__(self):
        self.events: list[ProductModerationEventSchema] = []

    async def send_product_event(self, event: ProductModerationEventSchema) -> None:
        self.events.append(event)


@dataclass
class SKURouteFakes:
    products: FakeProductRepository
    skus: FakeSKURepository
    images: FakeSKUImageRepository
    characteristics: FakeSKUCharacteristicRepository
    moderation: FakeModerationRepository


class SKURouteProvider(Provider):
    def __init__(self, fakes: SKURouteFakes):
        super().__init__()
        self.fakes = fakes

    @provide(scope=Scope.REQUEST)
    def get_product_repository(self) -> ProductRepository:
        return self.fakes.products

    @provide(scope=Scope.REQUEST)
    def get_sku_repository(self) -> SKURepository:
        return self.fakes.skus

    @provide(scope=Scope.REQUEST)
    def get_sku_image_repository(self) -> SKUImageRepository:
        return self.fakes.images

    @provide(scope=Scope.REQUEST)
    def get_sku_characteristic_repository(self) -> SKUCharacteristicRepository:
        return self.fakes.characteristics

    @provide(scope=Scope.REQUEST)
    def get_moderation_repository(self) -> ModerationRepository:
        return self.fakes.moderation

    create_sku_use_case = provide(CreateSKUUseCase, scope=Scope.REQUEST)
    edit_sku_use_case = provide(EditSKUUseCase, scope=Scope.REQUEST)


@pytest.fixture
def product() -> ProductReadSchema:
    now = datetime.now(UTC)
    return ProductReadSchema(
        id=uuid4(),
        seller_id=uuid4(),
        title='iPhone 15 Pro Max',
        description='Флагманский смартфон Apple',
        status=ProductStatus.CREATED,
        deleted=False,
        blocked=False,
        category_id=uuid4(),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def route_fakes(product: ProductReadSchema) -> SKURouteFakes:
    return SKURouteFakes(
        products=FakeProductRepository(product),
        skus=FakeSKURepository(),
        images=FakeSKUImageRepository(),
        characteristics=FakeSKUCharacteristicRepository(),
        moderation=FakeModerationRepository(),
    )


@pytest.fixture
def client(route_fakes: SKURouteFakes, product: ProductReadSchema) -> TestClient:
    app = FastAPI()
    app.include_router(skus_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), SKURouteProvider(route_fakes))
    setup_dishka(container, app)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUserSchema(
        id=product.seller_id,
        role=UserRole.SELLER,
    )
    return TestClient(app)


def test_create_sku_route_returns_201(client: TestClient, route_fakes: SKURouteFakes, product: ProductReadSchema):
    response = client.post(
        '/api/v1/skus/create',
        json={
            'product_id': str(product.id),
            'name': '256 GB Black',
            'price': 100000,
            'stock_quantity': 5,
            'article': 'IPH15PM-256-BLK',
            'images': [{'url': '/s3/sku-front.jpg', 'ordering': 0}],
            'characteristics': [{'name': 'Цвет', 'value': 'Черный'}],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body['product_id'] == str(product.id)
    assert body['images'][0]['url'] == '/s3/sku-front.jpg'
    assert route_fakes.products.product.status == ProductStatus.ON_MODERATION
    assert len(route_fakes.moderation.events) == 1


def make_sku(product_id: UUID, reserved_quantity: int = 0) -> SKUReadSchema:
    now = datetime.now(UTC)
    return SKUReadSchema(
        id=uuid4(),
        product_id=product_id,
        name='256 GB Black',
        price=100_000,
        stock_quantity=10,
        reserved_quantity=reserved_quantity,
        article='IPH15PM-256-BLK',
        cost_price=80_000,
        discount=5,
        created_at=now,
        updated_at=now,
    )


def edit_payload() -> dict:
    return {
        'name': '256 GB Space Black',
        'price': 120000,
        'stock_quantity': 15,
        'article': 'IPH15PM-256-SBLK',
        'cost_price': 85000,
        'discount': 10,
        'images': [{'url': '/s3/sku-fixed.jpg', 'ordering': 0}],
        'characteristics': [{'name': 'Цвет', 'value': 'Чёрный'}],
    }


def test_edit_sku_route_preserves_reserved_quantity(
    client: TestClient, route_fakes: SKURouteFakes, product: ProductReadSchema
):
    sku = make_sku(product.id, reserved_quantity=4)
    route_fakes.skus.skus[sku.id] = sku
    route_fakes.products.product = route_fakes.products.product.model_copy(update={'status': ProductStatus.MODERATED})

    response = client.put(f'/api/v1/skus/{sku.id}', json=edit_payload())

    assert response.status_code == 200
    body = response.json()
    assert body['reserved_quantity'] == 4
    assert body['name'] == '256 GB Space Black'
    assert body['price'] == 120000
    assert route_fakes.products.product.status == ProductStatus.ON_MODERATION
    assert len(route_fakes.moderation.events) == 1
    assert route_fakes.moderation.events[0].event == 'EDITED'


def test_edit_sku_route_hard_blocked_returns_403(
    client: TestClient, route_fakes: SKURouteFakes, product: ProductReadSchema
):
    sku = make_sku(product.id)
    route_fakes.skus.skus[sku.id] = sku
    route_fakes.products.product = route_fakes.products.product.model_copy(
        update={'status': ProductStatus.HARD_BLOCKED}
    )

    response = client.put(f'/api/v1/skus/{sku.id}', json=edit_payload())

    assert response.status_code == 403
    assert response.json() == {'code': 'FORBIDDEN', 'message': 'Cannot edit SKU of hard-blocked product'}


def test_edit_sku_route_other_seller_returns_403(
    client: TestClient, route_fakes: SKURouteFakes, product: ProductReadSchema
):
    sku = make_sku(product.id)
    route_fakes.skus.skus[sku.id] = sku
    route_fakes.products.product = route_fakes.products.product.model_copy(update={'seller_id': uuid4()})

    response = client.put(f'/api/v1/skus/{sku.id}', json=edit_payload())

    assert response.status_code == 403
    assert response.json() == {'code': 'NOT_OWNER', 'message': 'SKU does not belong to the authenticated seller'}


def test_edit_sku_route_missing_returns_404(client: TestClient, route_fakes: SKURouteFakes):
    response = client.put(f'/api/v1/skus/{uuid4()}', json=edit_payload())

    assert response.status_code == 404
    assert response.json() == {'code': 'NOT_FOUND', 'message': 'SKU not found'}


def test_edit_sku_route_no_longer_returns_501(
    client: TestClient, route_fakes: SKURouteFakes, product: ProductReadSchema
):
    sku = make_sku(product.id)
    route_fakes.skus.skus[sku.id] = sku

    response = client.put(f'/api/v1/skus/{sku.id}', json=edit_payload())

    assert response.status_code != 501
