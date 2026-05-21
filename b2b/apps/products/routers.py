import uuid

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from apps.auth.schemas import ErrorResponseSchema
from apps.products.schemas.request import ProductCreateRequestSchema, ProductEditRequestSchema
from apps.products.schemas.response import ProductResponseSchema
from apps.products.use_cases import CreateProductUseCase, EditProductUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/products')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


@router.post(
    '',
    status_code=status.HTTP_201_CREATED,
    response_model=ProductResponseSchema,
    responses=error_responses,
)
@inject
async def create_product(
    data: ProductCreateRequestSchema,
    use_case: FromDishka[CreateProductUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.SELLER)),
) -> ProductResponseSchema:
    return await use_case(data, current_user)


@router.patch(
    '/{product_id}',
    status_code=status.HTTP_200_OK,
    response_model=ProductResponseSchema,
    responses=error_responses,
)
@inject
async def edit_product(
    product_id: uuid.UUID,
    data: ProductEditRequestSchema,
    use_case: FromDishka[EditProductUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.SELLER)),
) -> ProductResponseSchema:
    return await use_case(product_id, data, current_user)
