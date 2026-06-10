from apps.home.errors import BannerNotFoundError
from apps.home.repositories import BannerClickRepository, BannerRepository
from apps.home.schemas.db import BannerClickCreateSchema
from apps.home.schemas.request import BannerClickRequestSchema
from shared.auth_lib import AuthenticatedUserSchema


class ClickBannerUseCase:
    """POST /banner-events — фиксация клика по баннеру.

    Бизнес-правила (US-CART-04):
    - Без обязательной авторизации. Если в JWT есть BUYER — пишем его id; иначе user_id=NULL.
    - Клик по несуществующему баннеру → 400 (BannerNotFoundError).
    - Активность/расписание не проверяем — клик мог произойти на уже исчезающем баннере;
      ценность аналитики выше строгого matching'а.
    """

    def __init__(
        self,
        banner_repository: BannerRepository,
        banner_click_repository: BannerClickRepository,
    ):
        self.banner_repository = banner_repository
        self.banner_click_repository = banner_click_repository

    async def __call__(
        self,
        data: BannerClickRequestSchema,
        current_user: AuthenticatedUserSchema | None,
    ) -> None:
        if not await self.banner_repository.exists(data.banner_id):
            raise BannerNotFoundError()

        await self.banner_click_repository.create(
            BannerClickCreateSchema(
                banner_id=data.banner_id,
                user_id=current_user.id if current_user else None,
            )
        )
