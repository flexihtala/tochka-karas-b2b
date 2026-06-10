from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.home.schemas.db import (
    BannerClickCreateSchema,
    BannerClickReadSchema,
    BannerCreateSchema,
    BannerReadSchema,
)


class FakeBannerRepository:
    def __init__(self):
        self.by_id: dict[UUID, BannerReadSchema] = {}
        self.created: list[BannerCreateSchema] = []

    def add(self, banner: BannerReadSchema) -> None:
        self.by_id[banner.id] = banner

    async def create(self, data: BannerCreateSchema) -> BannerReadSchema:
        self.created.append(data)
        banner_id = data.id or uuid4()
        now = datetime.now(UTC)
        banner = BannerReadSchema(
            id=banner_id,
            title=data.title,
            image_url=data.image_url,
            link_url=data.link_url,
            priority=data.priority,
            is_active=data.is_active,
            schedule_start=data.schedule_start,
            schedule_end=data.schedule_end,
            created_at=now,
            updated_at=now,
        )
        self.by_id[banner_id] = banner
        return banner

    async def get_or_none(self, id_: UUID) -> BannerReadSchema | None:
        return self.by_id.get(id_)

    async def exists(self, banner_id: UUID) -> bool:
        return banner_id in self.by_id

    async def list_active(self, now: datetime) -> list[BannerReadSchema]:
        result = [
            banner
            for banner in self.by_id.values()
            if banner.is_active
            and (banner.schedule_start is None or banner.schedule_start <= now)
            and (banner.schedule_end is None or banner.schedule_end >= now)
        ]
        # priority DESC, created_at ASC — стабильная очерёдность при равном priority.
        return sorted(result, key=lambda b: (-b.priority, b.created_at))


class FakeBannerClickRepository:
    def __init__(self):
        self.by_id: dict[UUID, BannerClickReadSchema] = {}
        self.created: list[BannerClickCreateSchema] = []

    async def create(self, data: BannerClickCreateSchema) -> BannerClickReadSchema:
        self.created.append(data)
        click_id = data.id or uuid4()
        now = datetime.now(UTC)
        click = BannerClickReadSchema(
            id=click_id,
            banner_id=data.banner_id,
            user_id=data.user_id,
            created_at=now,
            updated_at=now,
        )
        self.by_id[click_id] = click
        return click
