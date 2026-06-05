from dishka import Provider, Scope, provide

from apps.cart.repositories import CartItemRepository, CartRepository
from apps.cart.use_cases import (
    AddItemUseCase,
    ClearCartUseCase,
    GetCartUseCase,
    MergeCartUseCase,
    RemoveItemUseCase,
    UpdateItemUseCase,
    ValidateCartUseCase,
)
from settings import B2CSettings
from shared.http_clients import ServiceClient


class CartProvider(Provider):
    cart_repository = provide(CartRepository, scope=Scope.REQUEST)
    cart_item_repository = provide(CartItemRepository, scope=Scope.REQUEST)

    add_item_use_case = provide(AddItemUseCase, scope=Scope.REQUEST)
    update_item_use_case = provide(UpdateItemUseCase, scope=Scope.REQUEST)
    remove_item_use_case = provide(RemoveItemUseCase, scope=Scope.REQUEST)
    get_cart_use_case = provide(GetCartUseCase, scope=Scope.REQUEST)
    merge_cart_use_case = provide(MergeCartUseCase, scope=Scope.REQUEST)
    clear_cart_use_case = provide(ClearCartUseCase, scope=Scope.REQUEST)
    validate_cart_use_case = provide(ValidateCartUseCase, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def get_b2b_service_client(self, settings: B2CSettings) -> ServiceClient:
        return ServiceClient(base_url=settings.b2b_url, service_key=settings.b2c_to_b2b_key)
