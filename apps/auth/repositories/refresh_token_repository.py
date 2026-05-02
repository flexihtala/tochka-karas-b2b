from uuid import UUID

from apps.auth.models import RefreshToken
from apps.auth.schemas.refresh_token import RefreshTokenCreateSchema, RefreshTokenReadSchema, RefreshTokenUpdateSchema
from db import DBCrudRepository


class RefreshTokenRepository(
    DBCrudRepository[RefreshToken, RefreshTokenCreateSchema, RefreshTokenReadSchema, RefreshTokenUpdateSchema]
):
    id_field_name = 'jti'

    async def get_by_jti(self, jti: UUID) -> RefreshTokenReadSchema | None:
        return await self.get_or_none(jti)

    async def delete_by_jti(self, jti: UUID) -> bool:
        return await self.delete(jti)
