from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from schemas import CreateUUIDSchema, ReadUUIDSchema, UpdateUUIDSchema


class FavoriteCreateSchema(CreateUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    product_id: UUID


class FavoriteReadSchema(ReadUUIDSchema):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    product_id: UUID
    created_at: datetime
    updated_at: datetime


class FavoriteUpdateSchema(UpdateUUIDSchema):
    """Заглушка — избранное не обновляется в текущем US, но требуется DBCrudRepository."""

    model_config = ConfigDict(from_attributes=True)
