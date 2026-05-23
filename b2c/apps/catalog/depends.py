"""Dishka-провайдер для catalog.

- B2BCatalogClient — ServiceClient + b2b_url/b2c_to_b2b_key из settings.
- Use-cases — REQUEST-scope.
"""

from dishka import Provider, Scope, provide

from apps.catalog.clients import B2BCatalogClient
from apps.catalog.use_cases import GetFacetsUseCase, ListProductsUseCase
from settings import B2CSettings
from shared.http_clients import ServiceClient


class CatalogProvider(Provider):
    list_products_use_case = provide(ListProductsUseCase, scope=Scope.REQUEST)
    get_facets_use_case = provide(GetFacetsUseCase, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def get_b2b_service_client(self, settings: B2CSettings) -> ServiceClient:
        return ServiceClient(base_url=settings.b2b_url, service_key=settings.b2c_to_b2b_key)

    @provide(scope=Scope.REQUEST)
    def get_b2b_catalog_client(self, service_client: ServiceClient) -> B2BCatalogClient:
        return B2BCatalogClient(service_client=service_client)
