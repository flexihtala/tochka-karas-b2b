from uuid import UUID

from pydantic import BaseModel


class EventAcceptedResponseSchema(BaseModel):
    """Минимальный ответ на принятое событие (202 Accepted).

    `ticket_id` заполняется, когда событие затронуло конкретный тикет (created/edited);
    для deleted/no-op остаётся None.
    """

    status: str = 'accepted'
    ticket_id: UUID | None = None
