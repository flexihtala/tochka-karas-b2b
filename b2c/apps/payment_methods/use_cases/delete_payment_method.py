from uuid import UUID

from apps.payment_methods.errors import PaymentMethodNotFoundError
from apps.payment_methods.repositories import PaymentMethodRepository
from shared.auth_lib import AuthenticatedUserSchema


class DeletePaymentMethodUseCase:
    """DELETE /buyers/me/payment-methods/{method_id}."""

    def __init__(self, payment_method_repository: PaymentMethodRepository):
        self.payment_method_repository = payment_method_repository

    async def __call__(self, method_id: UUID, current_user: AuthenticatedUserSchema) -> None:
        existing = await self.payment_method_repository.get_or_none(method_id)
        if existing is None or existing.buyer_id != current_user.id:
            raise PaymentMethodNotFoundError()

        await self.payment_method_repository.delete(method_id)
