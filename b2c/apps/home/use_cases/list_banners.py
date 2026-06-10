from datetime import UTC, datetime

from apps.home.repositories import BannerRepository
from apps.home.schemas.response import BannerResponseSchema


class ListBannersUseCase:
    """GET /catalog/banners — публичный список активных баннеров (unified B2C spec).

    Бизнес-правила:
    - Без авторизации.
    - Фильтр: is_active=true, расписание (schedule_start..schedule_end) попадает в текущий момент.
    - Сортировка: priority ASC (меньшее значение — выше в слайдере) — серверная логика,
      не часть контракта ответа.
    - Ответ — плоский массив Banner[] (без конверта).
    """

    def __init__(self, banner_repository: BannerRepository):
        self.banner_repository = banner_repository

    async def __call__(self) -> list[BannerResponseSchema]:
        banners = await self.banner_repository.list_active(datetime.now(UTC))
        return [BannerResponseSchema.model_validate(banner) for banner in banners]
