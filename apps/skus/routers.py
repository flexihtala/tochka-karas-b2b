import uuid

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from apps.auth.dependencies import get_current_user
from apps.auth.schemas import AuthenticatedUserSchema, ErrorResponseSchema
from apps.skus.schemas import SKUCreateRequestSchema, SKUEditRequestSchema, SKUResponseSchema
from apps.skus.use_cases import CreateSKUUseCase, EditSKUUseCase

router = APIRouter(prefix='/skus')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


@router.post(
    '/create', status_code=status.HTTP_201_CREATED, response_model=SKUResponseSchema, responses=error_responses
)
@inject
async def create_sku(
    data: SKUCreateRequestSchema,
    use_case: FromDishka[CreateSKUUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
) -> SKUResponseSchema:
    return await use_case(data, current_user)


@router.put(
    '/{sku_id}',
    status_code=status.HTTP_200_OK,
    response_model=SKUResponseSchema,
    responses=error_responses,
)
@inject
async def edit_sku(
    sku_id: uuid.UUID,
    data: SKUEditRequestSchema,
    use_case: FromDishka[EditSKUUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
) -> SKUResponseSchema:
    return await use_case(sku_id, data, current_user)
