from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.payment_methods.errors import PaymentMethodNotFoundError
from apps.payment_methods.schemas.db import PaymentMethodReadSchema
from apps.payment_methods.schemas.request import (
    PaymentMethodCreateRequestSchema,
    PaymentMethodUpdateRequestSchema,
)
from apps.payment_methods.use_cases import (
    CreatePaymentMethodUseCase,
    DeletePaymentMethodUseCase,
    ListPaymentMethodsUseCase,
    UpdatePaymentMethodUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.payment_methods.fakes import FakePaymentMethodRepository


def make_user() -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=UserRole.BUYER)


def make_method(buyer_id, is_default: bool = False, method_id=None) -> PaymentMethodReadSchema:
    now = datetime.now(UTC)
    return PaymentMethodReadSchema(
        id=method_id or uuid4(),
        buyer_id=buyer_id,
        brand='VISA',
        last4='4242',
        exp_year=2030,
        exp_month=12,
        is_default=is_default,
        created_at=now,
        updated_at=now,
    )


def create_request(is_default: bool = False) -> PaymentMethodCreateRequestSchema:
    return PaymentMethodCreateRequestSchema(
        brand='VISA',
        last4='4242',
        exp_year=2030,
        exp_month=12,
        is_default=is_default,
    )


@pytest.mark.anyio
async def test_create_payment_method_uses_jwt_buyer_id():
    user = make_user()
    repo = FakePaymentMethodRepository()
    use_case = CreatePaymentMethodUseCase(payment_method_repository=repo)

    result = await use_case(create_request(), user)

    assert result.buyer_id == user.id
    assert repo.created[0].buyer_id == user.id


@pytest.mark.anyio
async def test_create_payment_method_with_default_unsets_other_defaults():
    user = make_user()
    repo = FakePaymentMethodRepository()
    existing = make_method(buyer_id=user.id, is_default=True)
    repo.add(existing)

    use_case = CreatePaymentMethodUseCase(payment_method_repository=repo)
    await use_case(create_request(is_default=True), user)

    assert repo.default_unset_calls == [(user.id, None)]
    assert repo.by_id[existing.id].is_default is False


@pytest.mark.anyio
async def test_create_payment_method_only_stores_metadata():
    """Гарантируем что в схеме нет полей PAN/CVC. Pydantic должен принимать
    лишь brand/last4/exp_year/exp_month/is_default — никакие сырые данные карты.
    """
    fields = set(PaymentMethodCreateRequestSchema.model_fields.keys())
    assert fields == {'brand', 'last4', 'exp_year', 'exp_month', 'is_default'}


@pytest.mark.anyio
async def test_list_payment_methods_filters_by_buyer():
    user = make_user()
    other = make_user()
    repo = FakePaymentMethodRepository()
    own = make_method(buyer_id=user.id)
    foreign = make_method(buyer_id=other.id)
    repo.add(own)
    repo.add(foreign)

    use_case = ListPaymentMethodsUseCase(payment_method_repository=repo)
    result = await use_case(user)

    assert [m.id for m in result] == [own.id]


@pytest.mark.anyio
async def test_update_payment_method_rejects_foreign_buyer():
    user = make_user()
    other = make_user()
    repo = FakePaymentMethodRepository()
    foreign = make_method(buyer_id=other.id)
    repo.add(foreign)

    use_case = UpdatePaymentMethodUseCase(payment_method_repository=repo)

    with pytest.raises(PaymentMethodNotFoundError):
        await use_case(foreign.id, PaymentMethodUpdateRequestSchema(is_default=True), user)


@pytest.mark.anyio
async def test_update_payment_method_sets_default_and_unsets_others():
    user = make_user()
    repo = FakePaymentMethodRepository()
    other_default = make_method(buyer_id=user.id, is_default=True)
    target = make_method(buyer_id=user.id, is_default=False)
    repo.add(other_default)
    repo.add(target)

    use_case = UpdatePaymentMethodUseCase(payment_method_repository=repo)
    result = await use_case(target.id, PaymentMethodUpdateRequestSchema(is_default=True), user)

    assert result.is_default is True
    assert repo.default_unset_calls == [(user.id, target.id)]
    assert repo.by_id[other_default.id].is_default is False


@pytest.mark.anyio
async def test_delete_payment_method_rejects_foreign_buyer():
    user = make_user()
    other = make_user()
    repo = FakePaymentMethodRepository()
    foreign = make_method(buyer_id=other.id)
    repo.add(foreign)

    use_case = DeletePaymentMethodUseCase(payment_method_repository=repo)

    with pytest.raises(PaymentMethodNotFoundError):
        await use_case(foreign.id, user)

    assert foreign.id in repo.by_id


@pytest.mark.anyio
async def test_delete_payment_method_removes_owned_method():
    user = make_user()
    repo = FakePaymentMethodRepository()
    own = make_method(buyer_id=user.id)
    repo.add(own)

    use_case = DeletePaymentMethodUseCase(payment_method_repository=repo)
    await use_case(own.id, user)

    assert own.id not in repo.by_id
