import uuid

from fastapi import APIRouter, Response, status

router = APIRouter(prefix='/skus')


@router.post('/', status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_sku() -> Response:
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.put('/{sku_id}', status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def edit_sku(sku_id: uuid.UUID) -> Response:
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)
