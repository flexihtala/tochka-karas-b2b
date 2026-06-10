"""Входящий канал событий от B2B.

- POST /api/v1/b2b/events — путь единой спеки (202 Accepted).
- POST /api/v1/events/product — канонный путь Flow B2C-12 (200 {accepted: true}).
Оба маршрута ведут в один use case. Аутентификация: X-Service-Key
+ direction = b2b_to_b2c (shared.inbox.make_verify_service_key).
"""

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends

from apps.auth.schemas import ErrorResponseSchema
from apps.events.schemas import ProductEventRequestSchema, ProductEventResponseSchema
from apps.events.use_cases import HandleProductEventUseCase
from settings import settings
from shared.inbox import make_verify_service_key
from shared.types import ServiceKeyDirection

# Без префикса: маршруты объявляются полными путями (/b2b/events и /events/product),
# router монтируется с общим /api/v1 в apps.router.
router = APIRouter()

# Конструируем FastAPI-зависимость один раз при импорте.
verify_b2b_to_b2c = make_verify_service_key(
    ServiceKeyDirection.B2B_TO_B2C,
    settings.b2b_to_b2c_key,
)


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
}


@router.post(
    '/b2b/events',
    response_model=ProductEventResponseSchema,
    status_code=202,
    responses=error_responses,
    dependencies=[Depends(verify_b2b_to_b2c)],
)
@inject
async def receive_product_event(
    payload: ProductEventRequestSchema,
    use_case: FromDishka[HandleProductEventUseCase],
) -> ProductEventResponseSchema:
    return await use_case(payload)


@router.post(
    '/events/product',
    response_model=ProductEventResponseSchema,
    status_code=200,
    responses=error_responses,
    dependencies=[Depends(verify_b2b_to_b2c)],
)
@inject
async def receive_product_event_canon(
    payload: ProductEventRequestSchema,
    use_case: FromDishka[HandleProductEventUseCase],
) -> ProductEventResponseSchema:
    """POST /api/v1/events/product — канонный путь (Flow B2C-12), 200 {accepted: true}."""
    return await use_case(payload)
