"""US-ORD-01: POST /api/v1/orders — checkout (cart-based, spec OpenAPI).

Auth: Bearer JWT, role BUYER. user_id берётся из JWT (никогда из body/query).
`Idempotency-Key` — обязательный заголовок (b2c openapi.yaml). Отсутствие/невалидный
UUID → 400 INVALID_REQUEST (RequestValidationError → validation_error_handler).
"""

from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Header, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.cart.schemas.response import CartValidationResponseSchema
from apps.orders.schemas import OrderCreateRequestSchema, OrderResponseSchema
from apps.orders.use_cases import CheckoutUseCase
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
