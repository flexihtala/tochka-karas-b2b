from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from apps.home.errors import BannerNotFoundError
from apps.home.schemas.db import BannerReadSchema
from apps.home.schemas.request import BannerClickRequestSchema
from apps.home.use_cases import ClickBannerUseCase, ListBannersUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.home.fakes import FakeBannerClickRepository, FakeBannerRepository


def make_banner(
    *,
    priority: int = 0,
    is_active: bool = True,
    schedule_start: datetime | None = None,
    schedule_end: datetime | None = None,
    banner_id: UUID | None = None,
    title: str | None = None,
) -> BannerReadSchema:
    now = datetime.now(UTC)
    return BannerReadSchema(
        id=banner_id or uuid4(),
        title=title or f'Banner {priority}',
        image_url='https://cdn.example.com/banner.png',
        link_url='https://example.com/landing',
        priority=priority,
        is_active=is_active,
        schedule_start=schedule_start,
        schedule_end=schedule_end,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.anyio
async def test_active_banners_returned_sorted_by_priority():
    """Активные баннеры (с учётом расписания) отдаются в priority ASC (меньше — выше)."""
    now = datetime.now(UTC)
    repo = FakeBannerRepository()

    low = make_banner(priority=1, title='Low')
    high = make_banner(priority=10, title='High')
    mid = make_banner(priority=5, title='Mid')
    scheduled_now = make_banner(
        priority=7,
        title='Scheduled',
        schedule_start=now - timedelta(hours=1),
        schedule_end=now + timedelta(hours=1),
    )
    expired = make_banner(
        priority=100,
        title='Expired',
        schedule_end=now - timedelta(days=1),
    )
    future = make_banner(
        priority=100,
        title='Future',
        schedule_start=now + timedelta(days=1),
    )
    inactive = make_banner(priority=99, title='Inactive', is_active=False)
    for b in [low, high, mid, scheduled_now, expired, future, inactive]:
        repo.add(b)

    use_case = ListBannersUseCase(banner_repository=repo)
    result = await use_case()

    # Только активные и попадающие в расписание; сортировка ASC по priority (wire-поле — ordering).
    assert [r.title for r in result] == ['Low', 'Mid', 'Scheduled', 'High']
    assert [r.ordering for r in result] == [1, 5, 7, 10]


@pytest.mark.anyio
async def test_no_active_banners_returns_200_empty():
    """Если активных баннеров нет — отдаётся пустой список (статус 200 на уровне router)."""
    repo = FakeBannerRepository()
    # Пара неактивных/просроченных, чтобы убедиться, что они не просочились.
    repo.add(make_banner(is_active=False))
    repo.add(
        make_banner(
            schedule_end=datetime.now(UTC) - timedelta(days=1),
        )
    )

    use_case = ListBannersUseCase(banner_repository=repo)
    result = await use_case()

    assert result == []


@pytest.mark.anyio
async def test_click_on_unknown_banner_returns_400():
    """Клик по несуществующему banner_id → BannerNotFoundError (status 400)."""
    banner_repo = FakeBannerRepository()
    click_repo = FakeBannerClickRepository()
    use_case = ClickBannerUseCase(banner_repository=banner_repo, banner_click_repository=click_repo)

    with pytest.raises(BannerNotFoundError) as exc_info:
        await use_case(BannerClickRequestSchema(banner_id=uuid4()), None)

    assert exc_info.value.status_code == 400
    assert click_repo.created == []


@pytest.mark.anyio
async def test_click_on_existing_banner_persists_event_for_anonymous():
    """Анонимный клик: user_id = None, запись создаётся."""
    banner = make_banner()
    banner_repo = FakeBannerRepository()
    banner_repo.add(banner)
    click_repo = FakeBannerClickRepository()

    use_case = ClickBannerUseCase(banner_repository=banner_repo, banner_click_repository=click_repo)
    await use_case(BannerClickRequestSchema(banner_id=banner.id), None)

    assert len(click_repo.created) == 1
    assert click_repo.created[0].banner_id == banner.id
    assert click_repo.created[0].user_id is None


@pytest.mark.anyio
async def test_click_on_existing_banner_uses_jwt_user_id_when_authorised():
    """Авторизованный клик: user_id берётся из JWT.id."""
    banner = make_banner()
    banner_repo = FakeBannerRepository()
    banner_repo.add(banner)
    click_repo = FakeBannerClickRepository()

    user = AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)
    use_case = ClickBannerUseCase(banner_repository=banner_repo, banner_click_repository=click_repo)
    await use_case(BannerClickRequestSchema(banner_id=banner.id), user)

    assert click_repo.created[0].user_id == user.id
