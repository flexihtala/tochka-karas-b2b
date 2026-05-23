from dishka import Provider, Scope, provide

from apps.payment_methods.repositories import PaymentMethodRepository
from apps.payment_methods.use_cases import (
    CreatePaymentMethodUseCase,
    DeletePaymentMethodUseCase,
    ListPaymentMethodsUseCase,
    UpdatePaymentMethodUseCase,
)


class PaymentMethodsProvider(Provider):
    payment_method_repository = provide(PaymentMethodRepository, scope=Scope.REQUEST)
    list_payment_methods_use_case = provide(ListPaymentMethodsUseCase, scope=Scope.REQUEST)
    create_payment_method_use_case = provide(CreatePaymentMethodUseCase, scope=Scope.REQUEST)
    update_payment_method_use_case = provide(UpdatePaymentMethodUseCase, scope=Scope.REQUEST)
    delete_payment_method_use_case = provide(DeletePaymentMethodUseCase, scope=Scope.REQUEST)
