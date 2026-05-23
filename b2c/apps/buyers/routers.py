from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from apps.auth.schemas import ErrorResponseSchema
from apps.buyers.schemas import BuyerResponseSchema, BuyerUpdateRequestSchema
from apps.buyers.use_cases import GetBuyerUseCase, UpdateBuyerUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/buyers')

error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


@router.get('/me', response_model=BuyerResponseSchema, responses=error_responses)
@inject
async def get_me(
    use_case: FromDishka[GetBuyerUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> BuyerResponseSchema:
    return await use_case(current_user)


@router.patch('/me', response_model=BuyerResponseSchema, responses=error_responses)
@inject
async def patch_me(
    data: BuyerUpdateRequestSchema,
    use_case: FromDishka[UpdateBuyerUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.BUYER)),
) -> BuyerResponseSchema:
    return await use_case(data, current_user)
