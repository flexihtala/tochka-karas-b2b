from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from apps.subscriptions.enums import NotifyOn


class SubscriptionCreateRequestSchema(BaseModel):
    """Тело запроса POST /api/v1/subscriptions.

    notify_on — список событий (PRICE_DROP / BACK_IN_STOCK). Минимум одно.
    """

    product_id: UUID
    notify_on: list[str] = Field(min_length=1)

    @field_validator('notify_on')
    @classmethod
    def validate_notify_on(cls, value: list[str]) -> list[str]:
        allowed = {item.value for item in NotifyOn}
        for event in value:
            if event not in allowed:
                raise ValueError(f'notify_on must be one of {sorted(allowed)}')
        # Дедупликация с сохранением порядка
        seen: set[str] = set()
        deduped: list[str] = []
        for event in value:
            if event not in seen:
                seen.add(event)
                deduped.append(event)
        return deduped
