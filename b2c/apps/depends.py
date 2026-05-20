from dishka import Provider, Scope, provide

from apps.addresses.depends import AddressesProvider
from apps.auth.depends import AuthProvider
from apps.buyers.depends import BuyersProvider
from apps.orders.depends import OrdersProvider
from apps.outbox.depends import OutboxProvider
from apps.payment_methods.depends import PaymentMethodsProvider
from shared.db import SessionManager
from settings import B2CSettings, settings


class CoreProvider(Provider):
    @provide(scope=Scope.APP)
    def get_settings(self) -> B2CSettings:
        return settings

    @provide(scope=Scope.APP)
    def get_session_manager(self, settings: B2CSettings) -> SessionManager:
        return SessionManager(settings)


providers = [
    CoreProvider(),
    AuthProvider(),
    BuyersProvider(),
    AddressesProvider(),
    PaymentMethodsProvider(),
    OrdersProvider(),
    OutboxProvider(),
]
