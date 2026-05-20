import uuid

from fastapi import APIRouter, Response, status

router = APIRouter(prefix='/products')


@router.post('/', status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_product() -> Response:
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.put('/{product_id}', status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def edit_product(product_id: uuid.UUID) -> Response:
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)
