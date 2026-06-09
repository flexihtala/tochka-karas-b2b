from dishka import Provider, Scope, provide

from apps.favorites.repositories import FavoriteRepository
from apps.favorites.use_cases import (
    AddFavoriteUseCase,
    B2BProductsClient,
    ListFavoritesUseCase,
    RemoveFavoriteUseCase,
)
from settings import B2CSettings
from shared.http_clients import ServiceClient


class FavoritesProvider(Provider):
    favorite_repository = provide(FavoriteRepository, scope=Scope.REQUEST)
    add_favorite_use_case = provide(AddFavoriteUseCase, scope=Scope.REQUEST)
    remove_favorite_use_case = provide(RemoveFavoriteUseCase, scope=Scope.REQUEST)
    list_favorites_use_case = provide(ListFavoritesUseCase, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def get_b2b_service_client(self, settings: B2CSettings) -> ServiceClient:
        return ServiceClient(
            base_url=settings.b2b_url,
            service_key=settings.b2c_to_b2b_key,
        )

    @provide(scope=Scope.REQUEST)
    def get_b2b_products_client(self, service_client: ServiceClient) -> B2BProductsClient:
        return B2BProductsClient(service_client=service_client)
