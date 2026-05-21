"""POST /api/v1/b2b/events — входящий канал событий от B2B.

Per spec (neomarket-protocols/b2c/openapi.yaml). Аутентификация: X-Service-Key
+ direction = b2b_to_b2c. См. canon Flow B2C-12 и shared.inbox.make_verify_service_key.
Spec response: 202 Accepted.
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

# Per spec: путь /api/v1/b2b/events. Router монтируется с общим /api/v1 в apps.router.
router = APIRouter(prefix='/b2b')

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
    '/events',
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
