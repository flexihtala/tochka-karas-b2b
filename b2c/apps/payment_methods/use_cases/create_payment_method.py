from apps.payment_methods.repositories import PaymentMethodRepository
from apps.payment_methods.schemas.db import PaymentMethodCreateSchema
from apps.payment_methods.schemas.request import PaymentMethodCreateRequestSchema
from apps.payment_methods.schemas.response import PaymentMethodResponseSchema
from shared.auth_lib import AuthenticatedUserSchema


class CreatePaymentMethodUseCase:
    """POST /buyers/me/payment-methods.

    Бизнес-правила:
    - buyer_id из JWT.
    - При is_default=True снимаем дефолт с остальных методов покупателя.
    - Принимаем ТОЛЬКО метаданные карты — никакого PAN/CVC.
    """

    def __init__(self, payment_method_repository: PaymentMethodRepository):
        self.payment_method_repository = payment_method_repository

    async def __call__(
        self,
        data: PaymentMethodCreateRequestSchema,
        current_user: AuthenticatedUserSchema,
    ) -> PaymentMethodResponseSchema:
        if data.is_default:
            await self.payment_method_repository.unset_default_for_buyer(current_user.id)

        method = await self.payment_method_repository.create(
            PaymentMethodCreateSchema(
                buyer_id=current_user.id,
                brand=data.brand,
                last4=data.last4,
                exp_year=data.exp_year,
                exp_month=data.exp_month,
                is_default=data.is_default,
            )
        )
        return PaymentMethodResponseSchema.model_validate(method)
