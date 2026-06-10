from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response, status

from apps.auth.dependencies import get_current_user
from apps.auth.schemas import (
    AuthTokensResponseSchema,
    ErrorResponseSchema,
    LoginRequestSchema,
    LogoutRequestSchema,
    RefreshRequestSchema,
    RefreshTokensResponseSchema,
)
from apps.auth.use_cases import LoginUseCase, LogoutUseCase, RefreshUseCase
from shared.auth_lib import AuthenticatedUserSchema

router = APIRouter(prefix='/auth')


error_responses = {
    400: {'model': ErrorResponseSchema},
    401: {'model': ErrorResponseSchema},
    403: {'model': ErrorResponseSchema},
}


@router.post('/login', response_model=AuthTokensResponseSchema, responses=error_responses)
@inject
async def login(data: LoginRequestSchema, use_case: FromDishka[LoginUseCase]) -> AuthTokensResponseSchema:
    return await use_case(data)


@router.post('/refresh', response_model=RefreshTokensResponseSchema, responses=error_responses)
@inject
async def refresh(data: RefreshRequestSchema, use_case: FromDishka[RefreshUseCase]) -> RefreshTokensResponseSchema:
    return await use_case(data)


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT, responses=error_responses)
@inject
async def logout(
    data: LogoutRequestSchema,
    use_case: FromDishka[LogoutUseCase],
    current_user: AuthenticatedUserSchema = Depends(get_current_user),
) -> Response:
    await use_case(data, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
