import uuid

from fastapi import APIRouter
from dishka import FromDishka

router = APIRouter(prefix='/skus')


@router.post('/')
async def create_sku(use_case: FromDishka[...]): ...


@router.put('/{sku_id}')
async def edit_sku(sku_id: uuid.UUID, use_case: FromDishka[...]): ...
