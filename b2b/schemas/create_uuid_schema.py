from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CreateUUIDSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
