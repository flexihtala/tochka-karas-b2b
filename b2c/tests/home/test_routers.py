from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.errors import setup_error_handlers
from apps.home.errors import BannerNotFoundError
from apps.home.routers import router as home_router
from apps.home.schemas.request import BannerClickRequestSchema
from apps.home.schemas.response import BannerResponseSchema
from apps.home.use_cases import ClickBannerUseCase, ListBannersUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole


def _make_banner(banner_id: UUID | None = None, priority: int = 0) -> BannerResponseSchema:
    # Build using DB-style aliases (link_url/priority/schedule_*) — model accepts
    # them via validation_alias for backwards compat with from_attributes().
    return BannerResponseSchema.model_validate(
        {
            'id': banner_id or uuid4(),
            'title': 'Promo',
            'image_url': 'https://cdn.example.com/banner.png',
            'link_url': 'https://example.com/landing',
            'priority': priority,
            'is_active': True,
            'schedule_start': None,
            'schedule_end': None,
            'created_at': datetime.now(UTC),
            'updated_at': datetime.now(UTC),
        }
    )


class StubListBanners:
    def __init__(self):
        self.calls = 0
        self.response: list[BannerResponseSchema] = []

    async def __call__(self) -> list[BannerResponseSchema]:
        self.calls += 1
        return self.response


class StubClickBanner:
    def __init__(self):
        self.calls: list[tuple[BannerClickRequestSchema, AuthenticatedUserSchema | None]] = []
        self.error: Exception | None = None

    async def __call__(
        self,
        data: BannerClickRequestSchema,
        current_user: AuthenticatedUserSchema | None,
    ) -> None:
        self.calls.append((data, current_user))
        if self.error:
            raise self.error


class HomeRouteProvider(Provider):
    def __init__(self, list_stub: StubListBanners, click_stub: StubClickBanner):
        super().__init__()
        self.list_stub = list_stub
        self.click_stub = click_stub

    @provide(scope=Scope.REQUEST)
    def get_list_use_case(self) -> ListBannersUseCase:
        return self.list_stub

    @provide(scope=Scope.REQUEST)
    def get_click_use_case(self) -> ClickBannerUseCase:
        return self.click_stub


def _make_app(
    list_stub: StubListBanners,
    click_stub: StubClickBanner,
    user: AuthenticatedUserSchema | None,
) -> FastAPI:
    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(home_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(FastapiProvider(), HomeRouteProvider(list_stub, click_stub))
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs():
    return StubListBanners(), StubClickBanner()


def test_no_active_banners_returns_200_empty(stubs):
    """GET /api/v1/catalog/banners без активных баннеров → 200 и плоский []."""
    list_stub, click_stub = stubs
    list_stub.response = []
    client = TestClient(_make_app(list_stub, click_stub, user=None))

    response = client.get('/api/v1/catalog/banners')

    assert response.status_code == 200
    assert response.json() == []
    assert list_stub.calls == 1


def test_list_catalog_banners_returns_flat_array_without_auth(stubs):
    list_stub, click_stub = stubs
    list_stub.response = [_make_banner(priority=1), _make_banner(priority=5)]
    client = TestClient(_make_app(list_stub, click_stub, user=None))

    response = client.get('/api/v1/catalog/banners')

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2
    # Spec-форма карточки баннера: id/title/image_url/link/ordering/active_from/active_to.
    first = body[0]
    assert first['ordering'] == 1
    assert first['link'] == 'https://example.com/landing'
    assert 'active_from' in first
    assert 'active_to' in first
    assert 'priority' not in first
    assert 'items' not in first


def test_post_banner_event_returns_204_anonymous(stubs):
    list_stub, click_stub = stubs
    banner_id = uuid4()
    client = TestClient(_make_app(list_stub, click_stub, user=None))

    response = client.post('/api/v1/banner-events', json={'banner_id': str(banner_id)})

    assert response.status_code == 204
    assert response.text == ''
    data, current_user = click_stub.calls[0]
    assert data.banner_id == banner_id
    assert current_user is None


def test_post_banner_event_uses_jwt_user_when_authenticated(stubs):
    list_stub, click_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    client = TestClient(_make_app(list_stub, click_stub, user=user))

    response = client.post('/api/v1/banner-events', json={'banner_id': str(uuid4())})

    assert response.status_code == 204
    _, current_user = click_stub.calls[0]
    assert current_user is not None
    assert current_user.id == user.id


def test_post_banner_event_unknown_banner_returns_400(stubs):
    list_stub, click_stub = stubs
    click_stub.error = BannerNotFoundError()
    client = TestClient(_make_app(list_stub, click_stub, user=None))

    response = client.post('/api/v1/banner-events', json={'banner_id': str(uuid4())})

    assert response.status_code == 400
    assert response.json() == {'code': 'BANNER_NOT_FOUND', 'message': 'Баннер не найден'}


def test_post_banner_event_invalid_payload_returns_400(stubs):
    list_stub, click_stub = stubs
    client = TestClient(_make_app(list_stub, click_stub, user=None))

    response = client.post('/api/v1/banner-events', json={})

    assert response.status_code == 400
    assert response.json() == {'code': 'INVALID_REQUEST', 'message': 'Невалидное тело запроса'}
