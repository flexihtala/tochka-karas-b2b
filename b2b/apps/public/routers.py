"""US-B2B-07: GET /api/v1/catalog/products — service-to-service витрина для B2C.

Auth: только X-Service-Key (b2c_to_b2b). JWT не используется.
"""

from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from apps.auth.schemas import ErrorResponseSchema
from apps.public.schemas.response import ProductPublicPaginatedResponseSchema
from apps.public.use_cases import ListCatalogUseCase
from settings import settings
from shared.errors.base import InvalidRequestError
from shared.inbox.dependencies import make_verify_service_key
from shared.types import ServiceKeyDirection

router = APIRouter(prefix='/catalog')

verify_b2c_to_b2b = make_verify_service_key(ServiceKeyDirection.B2C_TO_B2B, settings.b2c_to_b2b_key)


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
}


def _parse_ids(ids: str | None) -> list[UUID] | None:
    """Парсит query-параметр ?ids=uuid1,uuid2 в список UUID.

    Возвращает None, если параметр отсутствует (значит, обычный листинг).
    Пустая строка ?ids= интерпретируется как пустой список → пустая выдача.

    На невалидном UUID кидает InvalidRequestError (handled → 400 INVALID_REQUEST).
    """
    if ids is None:
        return None
    raw_parts = [part.strip() for part in ids.split(',')]
    parts = [part for part in raw_parts if part]
    try:
        return [UUID(part) for part in parts]
    except ValueError as exc:
        raise InvalidRequestError(message=f'Невалидный UUID в параметре ids: {exc}') from exc


@router.get(
    '/products',
    status_code=status.HTTP_200_OK,
    response_model=ProductPublicPaginatedResponseSchema,
    response_model_exclude_none=False,
    responses=error_responses,
    dependencies=[Depends(verify_b2c_to_b2b)],
)
@inject
async def list_catalog_products(
    use_case: FromDishka[ListCatalogUseCase],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ids: str | None = Query(default=None, description='Batch: список product_id через запятую'),
) -> ProductPublicPaginatedResponseSchema:
    parsed_ids = _parse_ids(ids)
    return await use_case(ids=parsed_ids, limit=limit, offset=offset)
