from uuid import UUID

from apps.auth.models import RefreshBlacklist
from apps.auth.schemas.refresh_blacklist import (
    RefreshBlacklistCreateSchema,
    RefreshBlacklistReadSchema,
    RefreshBlacklistUpdateSchema,
)
from db import DBCrudRepository


class RefreshBlacklistRepository(
    DBCrudRepository[
        RefreshBlacklist,
        RefreshBlacklistCreateSchema,
        RefreshBlacklistReadSchema,
        RefreshBlacklistUpdateSchema,
    ]
):
    id_field_name = 'jti'

    async def get_by_jti(self, jti: UUID) -> RefreshBlacklistReadSchema | None:
        return await self.get_or_none(jti)

    async def exists(self, jti: UUID) -> bool:
        return await self.get_by_jti(jti) is not None
