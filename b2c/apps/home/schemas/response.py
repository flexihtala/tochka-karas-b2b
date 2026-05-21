from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class BannerResponseSchema(BaseModel):
    """Banner response per openapi spec: id/image_url/link required.

    DB columns retain legacy names (link_url, priority, schedule_*); spec
    field names (link, ordering, active_from, active_to) are exposed via
    aliases so the wire format matches the openapi spec without a migration.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    title: str | None = None
    image_url: str
    link: str = Field(validation_alias=AliasChoices('link', 'link_url'))
    ordering: int = Field(default=0, validation_alias=AliasChoices('ordering', 'priority'))
    active_from: datetime | None = Field(
        default=None, validation_alias=AliasChoices('active_from', 'schedule_start')
    )
    active_to: datetime | None = Field(
        default=None, validation_alias=AliasChoices('active_to', 'schedule_end')
    )
