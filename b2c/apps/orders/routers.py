"""US-ORD-01: POST /api/v1/orders — checkout.

Auth: Bearer JWT, role BUYER. user_id берётся из JWT (никогда из body/query).
Per spec: `Idempotency-Key` header is required (b2c openapi.yaml).
"""

from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Header, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.orders.schemas import CheckoutRequestSchema, OrderResponseSchema
from apps.orders.use_cases import CheckoutUseCase
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
    idempotency_key_header: UUID | None = Header(default=None, alias='Idempotency-Key'),
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> OrderResponseSchema:
    # Spec: Idempotency-Key — header. Body-поле сохраняем для обратной совместимости,
    # но header имеет приоритет, если передан.
    if idempotency_key_header is not None:
        data = data.model_copy(update={'idempotency_key': idempotency_key_header})
    order, created = await use_case(data, current_user)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return order
