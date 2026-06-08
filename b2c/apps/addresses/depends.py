from dishka import Provider, Scope, provide

from apps.addresses.repositories import AddressRepository
from apps.addresses.use_cases import (
    CreateAddressUseCase,
    DeleteAddressUseCase,
    ListAddressesUseCase,
    UpdateAddressUseCase,
)


class AddressesProvider(Provider):
    address_repository = provide(AddressRepository, scope=Scope.REQUEST)
    list_addresses_use_case = provide(ListAddressesUseCase, scope=Scope.REQUEST)
    create_address_use_case = provide(CreateAddressUseCase, scope=Scope.REQUEST)
    update_address_use_case = provide(UpdateAddressUseCase, scope=Scope.REQUEST)
    delete_address_use_case = provide(DeleteAddressUseCase, scope=Scope.REQUEST)
