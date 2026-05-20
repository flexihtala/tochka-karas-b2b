from dishka import Provider, Scope, provide

from apps.home.repositories import (
    BannerClickRepository,
    BannerRepository,
    CollectionItemRepository,
    CollectionRepository,
)
from apps.home.services import B2BProductsClient
from apps.home.use_cases import (
    ClickBannerUseCase,
    GetCollectionProductsUseCase,
    ListBannersUseCase,
    ListCollectionsUseCase,
)
from settings import B2CSettings
from shared.http_clients import ServiceClient


class HomeProvider(Provider):
    banner_repository = provide(BannerRepository, scope=Scope.REQUEST)
    banner_click_repository = provide(BannerClickRepository, scope=Scope.REQUEST)
    collection_repository = provide(CollectionRepository, scope=Scope.REQUEST)
    collection_item_repository = provide(CollectionItemRepository, scope=Scope.REQUEST)

    list_banners_use_case = provide(ListBannersUseCase, scope=Scope.REQUEST)
    click_banner_use_case = provide(ClickBannerUseCase, scope=Scope.REQUEST)
    list_collections_use_case = provide(ListCollectionsUseCase, scope=Scope.REQUEST)
    get_collection_products_use_case = provide(GetCollectionProductsUseCase, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def get_b2b_service_client(self, settings: B2CSettings) -> ServiceClient:
        return ServiceClient(base_url=settings.b2b_url, service_key=settings.b2c_to_b2b_key)

    @provide(scope=Scope.REQUEST)
    def get_b2b_products_client(self, service_client: ServiceClient) -> B2BProductsClient:
        return B2BProductsClient(service_client=service_client)
