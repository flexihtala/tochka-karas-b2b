"""US-ORD-01: POST /api/v1/orders — checkout.

Auth: Bearer JWT, role BUYER. user_id берётся из JWT (никогда из body/query).
"""

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response, status

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
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> OrderResponseSchema:
    order, created = await use_case(data, current_user)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return order
