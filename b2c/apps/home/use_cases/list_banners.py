from datetime import UTC, datetime

from apps.home.repositories import BannerRepository
from apps.home.schemas.response import BannerResponseSchema


class ListBannersUseCase:
    """GET /home/banners — публичный список активных баннеров.

    Бизнес-правила:
    - Без авторизации.
    - Фильтр: is_active=true, расписание попадает в текущий момент времени.
    - Сортировка: priority DESC (большее число — выше).
    """

    def __init__(self, banner_repository: BannerRepository):
        self.banner_repository = banner_repository

    async def __call__(self) -> list[BannerResponseSchema]:
        banners = await self.banner_repository.list_active(datetime.now(UTC))
        return [BannerResponseSchema.model_validate(banner) for banner in banners]
