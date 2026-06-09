from uuid import UUID

from apps.cart.enums import CartValidationIssueType, UnavailableReason
from apps.cart.schemas.response import (
    CartItemResponseSchema,
    CartValidationIssueSchema,
    CartValidationResponseSchema,
)
from apps.cart.use_cases.get_cart import GetCartUseCase


class ValidateCartUseCase:
    """POST /api/v1/cart/validate — проверка корзины перед чекаутом.

    Переиспользует обогащение GetCartUseCase, затем строит issues:
    - недоступная позиция → issue OUT_OF_STOCK / PRODUCT_DELETED (по её reason).
    - доступная, но quantity > available_quantity → QUANTITY_REDUCED.
    is_valid = issues пуст (эквивалентно cart.is_valid).
    """

    def __init__(self, get_cart_use_case: GetCartUseCase):
        self.get_cart_use_case = get_cart_use_case

    async def __call__(
        self,
        *,
        user_id: UUID | None,
        session_id: str | None,
    ) -> CartValidationResponseSchema:
        cart = await self.get_cart_use_case(user_id=user_id, session_id=session_id)
        issues = [issue for item in cart.items if (issue := self._issue_for(item)) is not None]
        return CartValidationResponseSchema(is_valid=not issues, cart=cart, issues=issues)

    @staticmethod
    def _issue_for(item: CartItemResponseSchema) -> CartValidationIssueSchema | None:
        if not item.is_available:
            if item.unavailable_reason == UnavailableReason.PRODUCT_DELETED:
                return CartValidationIssueSchema(
                    sku_id=item.sku_id,
                    type=CartValidationIssueType.PRODUCT_DELETED,
                    message='Товар удалён или недоступен',
                )
            if item.unavailable_reason == UnavailableReason.PRODUCT_BLOCKED:
                return CartValidationIssueSchema(
                    sku_id=item.sku_id,
                    type=CartValidationIssueType.PRODUCT_BLOCKED,
                    message='Товар заблокирован',
                )
            return CartValidationIssueSchema(
                sku_id=item.sku_id,
                type=CartValidationIssueType.OUT_OF_STOCK,
                message='Нет в наличии',
            )

        if item.quantity > item.available_quantity:
            return CartValidationIssueSchema(
                sku_id=item.sku_id,
                type=CartValidationIssueType.QUANTITY_REDUCED,
                message='Доступное количество уменьшилось',
                old_value=item.quantity,
                new_value=item.available_quantity,
            )
        return None
