from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.payment_methods.schemas import (
    PaymentMethodCreateRequestSchema,
    PaymentMethodResponseSchema,
    PaymentMethodUpdateRequestSchema,
)
from apps.payment_methods.use_cases import (
    CreatePaymentMethodUseCase,
    DeletePaymentMethodUseCase,
    ListPaymentMethodsUseCase,
    UpdatePaymentMethodUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/buyers/me/payment-methods')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


@router.get('', response_model=list[PaymentMethodResponseSchema], responses=error_responses)
@inject
async def list_payment_methods(
    use_case: FromDishka[ListPaymentMethodsUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> list[PaymentMethodResponseSchema]:
    return await use_case(current_user)


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    response_model=PaymentMethodResponseSchema,
    responses=error_responses,
)
@inject
async def create_payment_method(
    data: PaymentMethodCreateRequestSchema,
    use_case: FromDishka[CreatePaymentMethodUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> PaymentMethodResponseSchema:
    return await use_case(data, current_user)


@router.patch('/{method_id}', response_model=PaymentMethodResponseSchema, responses=error_responses)
@inject
async def update_payment_method(
    method_id: UUID,
    data: PaymentMethodUpdateRequestSchema,
    use_case: FromDishka[UpdatePaymentMethodUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> PaymentMethodResponseSchema:
    return await use_case(method_id, data, current_user)


@router.delete('/{method_id}', status_code=status.HTTP_204_NO_CONTENT, responses=error_responses)
@inject
async def delete_payment_method(
    method_id: UUID,
    use_case: FromDishka[DeletePaymentMethodUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> Response:
    await use_case(method_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
