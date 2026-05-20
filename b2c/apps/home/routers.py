from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Request, Response, status

from apps.auth.schemas import ErrorResponseSchema
from apps.home.schemas import BannerClickRequestSchema, BannerResponseSchema
from apps.home.use_cases import ClickBannerUseCase, ListBannersUseCase
from shared.auth_lib import AuthenticatedUserSchema

router = APIRouter()


error_responses = {
    400: {'model': ErrorResponseSchema},
}


@router.get(
    '/home/banners',
    response_model=list[BannerResponseSchema],
    responses=error_responses,
)
@inject
async def list_home_banners(use_case: FromDishka[ListBannersUseCase]) -> list[BannerResponseSchema]:
    return await use_case()


@router.post(
    '/banner-events',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses,
)
@inject
async def post_banner_event(
    data: BannerClickRequestSchema,
    use_case: FromDishka[ClickBannerUseCase],
    request: Request,
) -> Response:
    user: AuthenticatedUserSchema | None = getattr(request.state, 'user', None)
    await use_case(data, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
