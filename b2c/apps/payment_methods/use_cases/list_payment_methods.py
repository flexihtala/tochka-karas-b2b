from apps.payment_methods.repositories import PaymentMethodRepository
from apps.payment_methods.schemas.response import PaymentMethodResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class ListPaymentMethodsUseCase:
    """GET /buyers/me/payment-methods — список платёжных методов покупателя."""

    def __init__(self, payment_method_repository: PaymentMethodRepository):
        self.payment_method_repository = payment_method_repository

    async def __call__(self, current_user: AuthenticatedUserSchema) -> list[PaymentMethodResponseSchema]:
        methods = await self.payment_method_repository.list_by_buyer(current_user.id)
        return [PaymentMethodResponseSchema.model_validate(method) for method in methods]
