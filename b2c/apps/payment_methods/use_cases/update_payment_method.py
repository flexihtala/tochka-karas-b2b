from uuid import UUID

from apps.payment_methods.errors import PaymentMethodNotFoundError
from apps.payment_methods.repositories import PaymentMethodRepository
from apps.payment_methods.schemas.db import PaymentMethodUpdateSchema
from apps.payment_methods.schemas.request import PaymentMethodUpdateRequestSchema
from apps.payment_methods.schemas.response import PaymentMethodResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class UpdatePaymentMethodUseCase:
    """PATCH /buyers/me/payment-methods/{method_id} — обновляет только is_default."""

    def __init__(self, payment_method_repository: PaymentMethodRepository):
        self.payment_method_repository = payment_method_repository

    async def __call__(
        self,
        method_id: UUID,
        data: PaymentMethodUpdateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> PaymentMethodResponseSchema:
        existing = await self.payment_method_repository.get_or_none(method_id)
        if existing is None or existing.buyer_id != current_user.id:
            raise PaymentMethodNotFoundError()

        update_payload = data.model_dump(exclude_unset=True)
        if data.is_default is True:
            await self.payment_method_repository.unset_default_for_buyer(current_user.id, except_id=method_id)

        if not update_payload:
            return PaymentMethodResponseSchema.model_validate(existing)

        updated = await self.payment_method_repository.update(PaymentMethodUpdateSchema(id=method_id, **update_payload))
        if updated is None:
            raise PaymentMethodNotFoundError()
        return PaymentMethodResponseSchema.model_validate(updated)
