import uuid

from fastapi import APIRouter
from dishka import FromDishka

router = APIRouter(prefix='/products')


@router.post('/')
async def create_product(use_case: FromDishka[...]): ...


@router.put('/{product_id}')
async def edit_product(product_id: uuid.UUID, use_case: FromDishka[...]): ...
