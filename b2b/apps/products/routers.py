from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.products.schemas.request import ProductCreateRequestSchema, ProductEditRequestSchema
from apps.products.schemas.response import ProductDetailResponseSchema, ProductResponseSchema
from apps.products.use_cases import (
    CreateProductUseCase,
    DeleteProductUseCase,
    EditProductUseCase,
    GetProductUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, UserRole, require_role

router = APIRouter(prefix='/products')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
    404: {'model': ErrorResponseSchema},
}


get_error_responses = {
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


@router.get(
    '/{product_id}',
    status_code=status.HTTP_200_OK,
    response_model=ProductDetailResponseSchema,
    responses=get_error_responses,
)
@inject
async def get_product(
    product_id: UUID,
    use_case: FromDishka[GetProductUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.SELLER)),
) -> ProductDetailResponseSchema:
    """Seller cabinet: карточка товара продавца (ProductDetailResponse).

    Чужой товар → 404 (НЕ 403): см. canon b2b-flows.md#view-product, защита
    от IDOR-by-discovery.
    """
    return await use_case(product_id, current_user)


@router.patch(
    '/{product_id}',
    status_code=status.HTTP_200_OK,
    response_model=ProductResponseSchema,
    responses=error_responses,
)
@inject
async def edit_product(
    product_id: UUID,
    data: ProductEditRequestSchema,
    use_case: FromDishka[EditProductUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.SELLER)),
) -> ProductResponseSchema:
    return await use_case(product_id, data, current_user)


@router.delete(
    '/{product_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses,
)
@inject
async def delete_product(
    product_id: UUID,
    use_case: FromDishka[DeleteProductUseCase],
    current_user: AuthenticatedUserSchema = Depends(require_role(UserRole.SELLER)),
) -> Response:
    await use_case(product_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
