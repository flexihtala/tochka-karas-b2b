from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Body, Depends, Response, status
from pydantic import BaseModel, Field, field_validator

from apps.auth.schemas import ErrorResponseSchema
from apps.subscriptions.enums import NotifyOn
from apps.subscriptions.schemas import SubscriptionCreateRequestSchema, SubscriptionResponseSchema
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
    """Тело подписки (канон): { notify_on: [BACK_IN_STOCK, PRICE_DROP] }.

    Минимум одно событие; пустой `[]` или невалидное значение → 400. Если поле
    не передано (нет тела) — подписываем на оба события по умолчанию.
    """

    notify_on: list[str] | None = Field(default=None)

    @field_validator('notify_on')
    @classmethod
    def validate_notify_on(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError('notify_on must not be empty')
        allowed = {item.value for item in NotifyOn}
        for event in value:
            if event not in allowed:
                raise ValueError(f'notify_on must be one of {sorted(allowed)}')
        return value


@router.post(
    '/{product_id}/subscribe',
    response_model=SubscriptionResponseSchema,
    responses=error_responses,
)
@inject
async def subscribe(
    product_id: UUID,
    use_case: FromDishka[SubscribeUseCase],
    response: Response,
    body: SubscribeBody | None = Body(default=None),
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> SubscriptionResponseSchema:
    """POST /api/v1/favorites/{product_id}/subscribe — подписка на товар.

    Канон b2c-cart-flows#b2c-7-subscriptions: **201** при создании, **409** если
    подписка уже существует. `notify_on` (BACK_IN_STOCK/PRICE_DROP) — минимум одно
    событие, пустой или невалидный → 400; если не передано — оба по умолчанию.
    user_id — ТОЛЬКО из JWT.
    """
    notify_on = body.notify_on if body and body.notify_on else list(DEFAULT_EVENTS)
    data = SubscriptionCreateRequestSchema(product_id=product_id, notify_on=notify_on)
    result = await use_case(data, current_user)
    response.status_code = status.HTTP_201_CREATED
    return result


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
