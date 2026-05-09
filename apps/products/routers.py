import uuid

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from apps.auth.dependencies import get_current_user
from apps.auth.schemas import AuthenticatedUserSchema, ErrorResponseSchema
from apps.products.schemas import ProductCreateRequestSchema, ProductEditRequestSchema, ProductResponseSchema
from apps.products.use_cases import CreateProductUseCase, EditProductUseCase

router = APIRouter(prefix='/products')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


@router.post('/', status_code=status.HTTP_201_CREATED, response_model=ProductResponseSchema, responses=error_responses)
@inject
async def create_product(
    data: ProductCreateRequestSchema,
    use_case: FromDishka[CreateProductUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
) -> ProductResponseSchema:
    return await use_case(data, current_user)


@router.put(
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
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
) -> ProductResponseSchema:
    return await use_case(product_id, data, current_user)
