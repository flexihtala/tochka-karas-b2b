from datetime import UTC, datetime

from apps.home.repositories import BannerRepository
from apps.home.schemas.response import BannerListResponseSchema, BannerResponseSchema


class ListBannersUseCase:
    """GET /home/banners — публичный список активных баннеров (канон B2C-14).

    Бизнес-правила:
    - Без авторизации.
    - Фильтр: is_active=true, расписание (start_at..end_at) попадает в текущий момент.
    - Сортировка: priority ASC (меньшее значение — выше в слайдере).
    - Ответ — конверт {items, total_count}.
    """

    def __init__(self, banner_repository: BannerRepository):
        self.banner_repository = banner_repository

    async def __call__(self) -> BannerListResponseSchema:
        banners = await self.banner_repository.list_active(datetime.now(UTC))
        items = [BannerResponseSchema.model_validate(banner) for banner in banners]
        return BannerListResponseSchema(items=items, total_count=len(items))
