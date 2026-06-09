from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Body, Depends, Response, status
from pydantic import BaseModel, Field, field_validator

from apps.auth.schemas import ErrorResponseSchema
from apps.subscriptions.enums import NotifyOn
from apps.subscriptions.schemas import SubscriptionCreateRequestSchema
from apps.subscriptions.use_cases import SubscribeUseCase, UnsubscribeUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/favorites')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
    409: {'model': ErrorResponseSchema},
}

DEFAULT_EVENTS: list[str] = ['BACK_IN_STOCK', 'PRICE_DROP']


class SubscribeBody(BaseModel):
    """Optional body per spec: { events: [BACK_IN_STOCK, PRICE_DROP] }."""

    events: list[str] | None = Field(default=None)

    @field_validator('events')
    @classmethod
    def validate_events(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        allowed = {item.value for item in NotifyOn}
        for event in value:
            if event not in allowed:
                raise ValueError(f'events must be one of {sorted(allowed)}')
        return value


@router.post(
    '/{product_id}/subscribe',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses,
)
@inject
async def subscribe(
    product_id: UUID,
    use_case: FromDishka[SubscribeUseCase],
    body: SubscribeBody | None = Body(default=None),
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> Response:
    """POST /api/v1/favorites/{product_id}/subscribe — подписка на товар.

    Per openapi spec: 204 No Content. Optional body {events: [...]}.
    """
    events = body.events if body and body.events else list(DEFAULT_EVENTS)
    data = SubscriptionCreateRequestSchema(product_id=product_id, notify_on=events)
    await use_case(data, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    '/{product_id}/subscribe',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses,
)
@inject
async def unsubscribe(
    product_id: UUID,
    use_case: FromDishka[UnsubscribeUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> Response:
    """DELETE /api/v1/favorites/{product_id}/subscribe — отписка."""
    await use_case(product_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
