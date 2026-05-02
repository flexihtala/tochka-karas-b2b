from fastapi import APIRouter
from dishka import FromDishka

router = APIRouter(prefix='/auth')


@router.post('/register')
async def register(use_case: FromDishka[...]): ...


@router.post('/refresh')
async def refresh(use_case: FromDishka[...]): ...


@router.post('/logout')
async def logout(use_case: FromDishka[...]): ...


@router.post('/login')
async def login(use_case: FromDishka[...]): ...
