from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UpdateUUIDSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
