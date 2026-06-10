"""US-ORD-01 / US-ORD-02 / US-ORD-03:

- POST /api/v1/orders               — checkout (US-ORD-01, cart-based, spec OpenAPI)
- GET  /api/v1/orders               — список заказов (US-ORD-02, paginated, ?status=)
- GET  /api/v1/orders/{order_id}    — детали заказа (US-ORD-02, цены из снапшота)
- POST /api/v1/orders/{order_id}/cancel — отмена (US-ORD-03)

Auth: Bearer JWT, role BUYER. user_id берётся из JWT (никогда из body/query).
`Idempotency-Key` — обязательный заголовок POST (b2c openapi.yaml). Отсутствие/невалидный
UUID → 400 INVALID_REQUEST (RequestValidationError → validation_error_handler).
Чужой заказ в GET /{order_id} → 404 (не 403) — IDOR-prevention по канону.
"""

from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Header, Query, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.cart.schemas.response import CartValidationResponseSchema
from apps.orders.schemas import (
    CancelRequestSchema,
    OrderCreateRequestSchema,
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
    409: {'model': ErrorResponseSchema},
    422: {'model': CartValidationResponseSchema},
    503: {'model': ErrorResponseSchema},
}


cancel_error_responses = {
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
    409: {'model': ErrorResponseSchema},
    503: {'model': ErrorResponseSchema},
}


view_error_responses = {
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


@router.post(
    '',
    response_model=OrderResponseSchema,
    responses=error_responses,
)
@inject
async def create_order(
    data: OrderCreateRequestSchema,
    response: Response,
    use_case: FromDishka[CheckoutUseCase],
    idempotency_key: UUID = Header(alias='Idempotency-Key'),
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> OrderResponseSchema:
    order, created = await use_case(
        idempotency_key=idempotency_key,
        data=data,
        current_user=current_user,
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return order


@router.get(
    '',
    response_model=OrderListResponseSchema,
    responses=view_error_responses,
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
    responses=view_error_responses,
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
    responses=cancel_error_responses,
)
@inject
async def cancel_order(
    order_id: UUID,
    use_case: FromDishka[CancelOrderUseCase],
    body: CancelRequestSchema | None = None,
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> OrderResponseSchema:
    return await use_case(order_id, current_user, reason=body.reason if body else None)
