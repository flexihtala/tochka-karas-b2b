import uuid

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.skus.schemas.request import SKUCreateRequestSchema, SKUEditRequestSchema
from apps.skus.schemas.response import SKUResponseSchema
from apps.skus.use_cases import CreateSKUUseCase, DeleteSKUUseCase, EditSKUUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/skus')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


delete_responses = {
    **error_responses,
    409: {'model': ErrorResponseSchema},
}


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    response_model=SKUResponseSchema,
    responses=error_responses,
)
@inject
async def create_sku(
    data: SKUCreateRequestSchema,
    use_case: FromDishka[CreateSKUUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.SELLER)),
) -> SKUResponseSchema:
    return await use_case(data, current_user)


@router.patch(
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
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.SELLER)),
) -> SKUResponseSchema:
    return await use_case(sku_id, data, current_user)


@router.delete(
    '/{sku_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=delete_responses,
)
@inject
async def delete_sku(
    sku_id: uuid.UUID,
    use_case: FromDishka[DeleteSKUUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.SELLER)),
) -> Response:
    await use_case(sku_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
