from uuid import UUID

from pydantic import BaseModel


class BannerClickRequestSchema(BaseModel):
    banner_id: UUID
