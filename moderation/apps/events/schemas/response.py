from uuid import UUID

from pydantic import BaseModel


class EventAcceptedResponseSchema(BaseModel):
    """Минимальный ответ на принятое событие. Кешируется в processed_events.response_cached
    для повторных запросов с тем же idempotency_key.
    """

    status: str = 'accepted'
    ticket_id: UUID | None = None
