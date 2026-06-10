from dishka import Provider, Scope, provide

from apps.orders.b2b_client import B2BInventoryClient
from apps.orders.repositories import OrderItemRepository, OrderRepository
from apps.orders.use_cases import CancelOrderUseCase, CheckoutUseCase, GetOrderUseCase, ListOrdersUseCase
from settings import B2CSettings
from shared.http_clients import ServiceClient


class OrdersProvider(Provider):
    order_repository = provide(OrderRepository, scope=Scope.REQUEST)
    order_item_repository = provide(OrderItemRepository, scope=Scope.REQUEST)
    checkout_use_case = provide(CheckoutUseCase, scope=Scope.REQUEST)
    cancel_order_use_case = provide(CancelOrderUseCase, scope=Scope.REQUEST)
    list_orders_use_case = provide(ListOrdersUseCase, scope=Scope.REQUEST)
    get_order_use_case = provide(GetOrderUseCase, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def get_b2b_service_client(self, settings: B2CSettings) -> ServiceClient:
        return ServiceClient(
            base_url=settings.b2b_url,
            service_key=settings.b2c_to_b2b_key,
        )

    @provide(scope=Scope.REQUEST)
    def get_b2b_inventory_client(self, service_client: ServiceClient) -> B2BInventoryClient:
        return B2BInventoryClient(service_client=service_client)
