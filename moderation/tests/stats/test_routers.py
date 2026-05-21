from uuid import uuid4

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.errors import setup_error_handlers
from apps.stats.routers import router as stats_router
from apps.stats.schemas.response import ModeratorStatsResponseSchema, StatsOverviewResponseSchema
from apps.stats.use_cases import ModeratorsStatsUseCase, OverviewStatsUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole


class StubOverviewUseCase:
    def __init__(self):
        self.calls: list[str | None] = []
        self.response = StatsOverviewResponseSchema(
            pending_count=3,
            in_review_count=1,
            approved_count=4,
            blocked_count=2,
            hard_blocked_count=1,
        )

    async def __call__(self, period: str | None = None) -> StatsOverviewResponseSchema:
        self.calls.append(period)
        return self.response


class StubModeratorsStatsUseCase:
    def __init__(self):
        self.calls: list[str | None] = []
        self.response: list[ModeratorStatsResponseSchema] = [
            ModeratorStatsResponseSchema(
                moderator_id=uuid4(),
                decisions_count=5,
                approved_count=3,
                blocked_count=2,
                hard_blocked_count=0,
            )
        ]

    async def __call__(self, period: str | None = None) -> list[ModeratorStatsResponseSchema]:
        self.calls.append(period)
        return self.response


class StatsRouteProvider(Provider):
    def __init__(self, overview_stub: StubOverviewUseCase, moderators_stub: StubModeratorsStatsUseCase):
        super().__init__()
        self.overview_stub = overview_stub
        self.moderators_stub = moderators_stub

    @provide(scope=Scope.REQUEST)
    def get_overview_use_case(self) -> OverviewStatsUseCase:
        return self.overview_stub  # type: ignore[return-value]

    @provide(scope=Scope.REQUEST)
    def get_moderators_use_case(self) -> ModeratorsStatsUseCase:
        return self.moderators_stub  # type: ignore[return-value]


def _make_app(
    overview_stub: StubOverviewUseCase,
    moderators_stub: StubModeratorsStatsUseCase,
    user: AuthenticatedUserSchema | None,
) -> FastAPI:
    class _UserInjector(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.user = user
            return await call_next(request)

    app = FastAPI()
    app.add_middleware(_UserInjector)
    app.include_router(stats_router, prefix='/api/v1')
    setup_error_handlers(app)
    container = make_async_container(
        FastapiProvider(),
        StatsRouteProvider(overview_stub, moderators_stub),
    )
    setup_dishka(container, app)
    return app


@pytest.fixture
def stubs() -> tuple[StubOverviewUseCase, StubModeratorsStatsUseCase]:
    return StubOverviewUseCase(), StubModeratorsStatsUseCase()


def test_overview_requires_authentication(stubs):
    overview_stub, moderators_stub = stubs
    client = TestClient(_make_app(overview_stub, moderators_stub, user=None))

    response = client.get('/api/v1/stats/overview')

    assert response.status_code == 401
    assert overview_stub.calls == []


def test_overview_rejects_seller_role(stubs):
    overview_stub, moderators_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.SELLER)
    client = TestClient(_make_app(overview_stub, moderators_stub, user))

    response = client.get('/api/v1/stats/overview')

    assert response.status_code == 403
    assert overview_stub.calls == []


def test_overview_allows_moderator(stubs):
    overview_stub, moderators_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.MODERATOR)
    client = TestClient(_make_app(overview_stub, moderators_stub, user))

    response = client.get('/api/v1/stats/overview?period=week')

    assert response.status_code == 200
    body = response.json()
    # Спека StatsOverview: per-status counts (без total_tickets).
    assert body['pending_count'] == 3
    assert body['hard_blocked_count'] == 1
    assert 'total_tickets' not in body
    assert overview_stub.calls == ['week']


def test_overview_default_period_is_today(stubs):
    overview_stub, moderators_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.ADMIN)
    client = TestClient(_make_app(overview_stub, moderators_stub, user))

    response = client.get('/api/v1/stats/overview')

    assert response.status_code == 200
    assert overview_stub.calls == ['today']


def test_moderators_stats_requires_auth(stubs):
    overview_stub, moderators_stub = stubs
    client = TestClient(_make_app(overview_stub, moderators_stub, user=None))

    response = client.get('/api/v1/stats/moderators')
    assert response.status_code == 401


def test_moderators_stats_returns_list(stubs):
    overview_stub, moderators_stub = stubs
    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.MODERATOR)
    client = TestClient(_make_app(overview_stub, moderators_stub, user))

    response = client.get('/api/v1/stats/moderators')

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]['decisions_count'] == 5
