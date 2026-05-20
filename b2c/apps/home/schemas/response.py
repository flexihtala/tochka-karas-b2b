from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BannerResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    image_url: str
    link_url: str
    priority: int
    is_active: bool
    schedule_start: datetime | None
    schedule_end: datetime | None
    created_at: datetime
    updated_at: datetime
