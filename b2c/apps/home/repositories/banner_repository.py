from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select

from apps.home.models import Banner
from apps.home.schemas.db import BannerCreateSchema, BannerReadSchema, BannerUpdateSchema
from shared.db import DBCrudRepository


class BannerRepository(DBCrudRepository[Banner, BannerCreateSchema, BannerReadSchema, BannerUpdateSchema]):
    async def list_active(self, now: datetime) -> list[BannerReadSchema]:
        """Активные баннеры с учётом расписания.

        is_active=true И (schedule_start IS NULL ИЛИ schedule_start <= now)
                       И (schedule_end   IS NULL ИЛИ schedule_end   >= now)
        Сортировка: priority DESC.
        """
        query = (
            select(Banner)
            .where(
                and_(
                    Banner.is_active.is_(True),
                    or_(Banner.schedule_start.is_(None), Banner.schedule_start <= now),
                    or_(Banner.schedule_end.is_(None), Banner.schedule_end >= now),
                )
            )
            .order_by(Banner.priority.desc(), Banner.created_at.asc())
        )

        async with self.session_manager.get_session() as session:
            models = (await session.execute(query)).scalars().all()

        return [self.model_validate(model) for model in models]

    async def exists(self, banner_id: UUID) -> bool:
        query = select(Banner.id).where(Banner.id == banner_id)
        async with self.session_manager.get_session() as session:
            return (await session.execute(query)).scalar_one_or_none() is not None
