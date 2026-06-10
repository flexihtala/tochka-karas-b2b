from dishka import Provider, Scope, provide

from apps.home.repositories import BannerClickRepository, BannerRepository
from apps.home.use_cases import ClickBannerUseCase, ListBannersUseCase


class HomeProvider(Provider):
    banner_repository = provide(BannerRepository, scope=Scope.REQUEST)
    banner_click_repository = provide(BannerClickRepository, scope=Scope.REQUEST)

    list_banners_use_case = provide(ListBannersUseCase, scope=Scope.REQUEST)
    click_banner_use_case = provide(ClickBannerUseCase, scope=Scope.REQUEST)
