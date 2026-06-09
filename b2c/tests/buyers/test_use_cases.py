from uuid import uuid4

import pytest

from apps.buyers.errors import BuyerNotFoundError
from apps.buyers.schemas.request import BuyerUpdateRequestSchema
from apps.buyers.use_cases import GetBuyerUseCase, UpdateBuyerUseCase
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.auth.fakes import FakeUserRepository, make_user_read_schema


def make_user(user_id=None) -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=user_id or uuid4(), role=UserRole.BUYER)


@pytest.mark.anyio
async def test_get_buyer_returns_profile():
    user = make_user()
    repo = FakeUserRepository()
    repo.add(make_user_read_schema(id=user.id))

    use_case = GetBuyerUseCase(user_repository=repo)
    result = await use_case(user)

    assert result.id == user.id
    assert result.email == 'buyer@example.com'


@pytest.mark.anyio
async def test_get_buyer_raises_when_missing():
    user = make_user()
    repo = FakeUserRepository()

    use_case = GetBuyerUseCase(user_repository=repo)

    with pytest.raises(BuyerNotFoundError):
        await use_case(user)


@pytest.mark.anyio
async def test_update_buyer_applies_partial_payload():
    user = make_user()
    repo = FakeUserRepository()
    repo.add(make_user_read_schema(id=user.id, first_name='Ivan'))

    use_case = UpdateBuyerUseCase(user_repository=repo)
    result = await use_case(BuyerUpdateRequestSchema(first_name='Petr'), user)

    assert result.first_name == 'Petr'
    assert repo.updated[-1]['first_name'] == 'Petr'


@pytest.mark.anyio
async def test_update_buyer_no_payload_returns_existing_profile():
    user = make_user()
    repo = FakeUserRepository()
    repo.add(make_user_read_schema(id=user.id, first_name='Ivan'))

    use_case = UpdateBuyerUseCase(user_repository=repo)
    result = await use_case(BuyerUpdateRequestSchema(), user)

    assert result.first_name == 'Ivan'
    # No update call should have been made.
    assert repo.updated == []


@pytest.mark.anyio
async def test_update_buyer_raises_when_user_missing():
    user = make_user()
    repo = FakeUserRepository()  # repo is empty

    use_case = UpdateBuyerUseCase(user_repository=repo)

    with pytest.raises(BuyerNotFoundError):
        await use_case(BuyerUpdateRequestSchema(first_name='Petr'), user)
