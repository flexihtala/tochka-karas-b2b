"""POST /api/v1/inventory/{reserve,unreserve}.

Service-to-service endpoints. Аутентификация — X-Service-Key, направление
b2c_to_b2b. Заголовок проверяется FastAPI-зависимостью.
"""

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from apps.auth.schemas import ErrorResponseSchema
from apps.inventory.depends import verify_b2c_to_b2b_service_key
from apps.inventory.schemas import (
    ReserveRequestSchema,
    ReserveResponseSchema,
    UnreserveRequestSchema,
    UnreserveResponseSchema,
)
from apps.inventory.use_cases import ReserveInventoryUseCase, UnreserveInventoryUseCase

router = APIRouter(prefix='/inventory')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    409: {'model': ErrorResponseSchema},
}


@router.post(
    '/reserve',
    status_code=status.HTTP_200_OK,
    response_model=ReserveResponseSchema,
    responses=error_responses,
    dependencies=[Depends(verify_b2c_to_b2b_service_key)],
)
@inject
async def reserve(
    data: ReserveRequestSchema,
    use_case: FromDishka[ReserveInventoryUseCase],
) -> ReserveResponseSchema:
    return await use_case(data)


@router.post(
    '/unreserve',
    status_code=status.HTTP_200_OK,
    response_model=UnreserveResponseSchema,
    responses=error_responses,
    dependencies=[Depends(verify_b2c_to_b2b_service_key)],
)
@inject
async def unreserve(
    data: UnreserveRequestSchema,
    use_case: FromDishka[UnreserveInventoryUseCase],
) -> UnreserveResponseSchema:
    return await use_case(data)
