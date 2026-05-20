"""US-ORD-01 / US-ORD-02 / US-ORD-03:
- POST   /api/v1/orders                  — checkout (US-ORD-01)
- GET    /api/v1/orders                  — list orders (US-ORD-02)
- GET    /api/v1/orders/{id}             — order detail (US-ORD-02)
- POST   /api/v1/orders/{id}/cancel      — cancel (US-ORD-03)

Auth: Bearer JWT, role BUYER. user_id из JWT (никогда из body/query).
"""

from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.orders.schemas import (
    CheckoutRequestSchema,
    OrderListResponseSchema,
    OrderResponseSchema,
)
from apps.orders.use_cases import CancelOrderUseCase, CheckoutUseCase, GetOrderUseCase, ListOrdersUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/orders')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
    409: {'model': ErrorResponseSchema},
    503: {'model': ErrorResponseSchema},
}


@router.post(
    '',
    response_model=OrderResponseSchema,
    responses=error_responses,
)
@inject
async def create_order(
    data: CheckoutRequestSchema,
    response: Response,
    use_case: FromDishka[CheckoutUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> OrderResponseSchema:
    order, created = await use_case(data, current_user)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return order


@router.get(
    '',
    response_model=OrderListResponseSchema,
    responses=error_responses,
)
@inject
async def list_orders(
    use_case: FromDishka[ListOrdersUseCase],
    status_filter: str | None = Query(default=None, alias='status'),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> OrderListResponseSchema:
    return await use_case(current_user, status=status_filter, limit=limit, offset=offset)


@router.get(
    '/{order_id}',
    response_model=OrderResponseSchema,
    responses=error_responses,
)
@inject
async def get_order(
    order_id: UUID,
    use_case: FromDishka[GetOrderUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> OrderResponseSchema:
    return await use_case(order_id, current_user)


@router.post(
    '/{order_id}/cancel',
    response_model=OrderResponseSchema,
    responses=error_responses,
)
@inject
async def cancel_order(
    order_id: UUID,
    use_case: FromDishka[CancelOrderUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> OrderResponseSchema:
    return await use_case(order_id, current_user)
