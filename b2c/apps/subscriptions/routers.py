from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.subscriptions.schemas import (
    SubscriptionCreateRequestSchema,
    SubscriptionResponseSchema,
)
from apps.subscriptions.use_cases import SubscribeUseCase, UnsubscribeUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/subscriptions')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
    409: {'model': ErrorResponseSchema},
}


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    response_model=SubscriptionResponseSchema,
    responses=error_responses,
)
@inject
async def subscribe(
    data: SubscriptionCreateRequestSchema,
    use_case: FromDishka[SubscribeUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> SubscriptionResponseSchema:
    return await use_case(data, current_user)


@router.delete('/{product_id}', status_code=status.HTTP_204_NO_CONTENT, responses=error_responses)
@inject
async def unsubscribe(
    product_id: UUID,
    use_case: FromDishka[UnsubscribeUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> Response:
    await use_case(product_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
