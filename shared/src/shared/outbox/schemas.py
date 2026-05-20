from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shared.outbox.enums import OutboxStatus
from shared.types import ServiceName


class OutboxEnqueueSchema(BaseModel):
    """Что передаёт use-case в OutboxRepository.enqueue()."""

    idempotency_key: UUID = Field(default_factory=lambda: UUID(int=0))  # use-case задаёт явно
    event_type: str
    target_service: ServiceName
    payload: dict[str, Any]


class OutboxEventReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    idempotency_key: UUID
    event_type: str
    target_service: str
    payload: dict[str, Any]
    status: OutboxStatus
    retry_count: int
    next_retry_at: datetime | None
    sent_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
