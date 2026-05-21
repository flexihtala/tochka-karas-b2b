from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class FieldReportSeverity(StrEnum):
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'


class FieldReportSchema(BaseModel):
    """FieldReport по спеке `neomarket-moderation.yaml`:
    field_path (обяз.), message (обяз.), severity (опц., default ERROR).
    """

    field_path: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=1000)
    severity: FieldReportSeverity = FieldReportSeverity.ERROR


class ApproveTicketRequestSchema(BaseModel):
    """POST /api/v1/tickets/{id}/approve — опциональное тело по спеке.

    Поле comment (maxLength 2000) — опциональный комментарий модератора при одобрении.
    """

    comment: str | None = Field(default=None, max_length=2000)


class BlockTicketRequestSchema(BaseModel):
    """POST /api/v1/tickets/{id}/block — тело запроса (BlockDecisionRequest по спеке).

    blocking_reason_ids — массив (minItems: 1) UUID причин.
    comment — опциональный комментарий модератора (maxLength 2000).
    hard_block выводится из выбранной причины — не передаётся в теле.
    """

    blocking_reason_ids: list[UUID] = Field(min_length=1)
    comment: str | None = Field(default=None, max_length=2000)
    field_reports: list[FieldReportSchema] | None = None
