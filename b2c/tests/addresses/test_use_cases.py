from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.addresses.errors import AddressNotFoundError
from apps.addresses.schemas.db import AddressReadSchema
from apps.addresses.schemas.request import AddressCreateRequestSchema, AddressUpdateRequestSchema
from apps.addresses.use_cases import (
    CreateAddressUseCase,
    DeleteAddressUseCase,
    ListAddressesUseCase,
    UpdateAddressUseCase,
)
from shared.auth_lib import AuthenticatedUserSchema, UserRole
from tests.addresses.fakes import FakeAddressRepository


def make_user(role: UserRole = UserRole.BUYER) -> AuthenticatedUserSchema:
    return AuthenticatedUserSchema(id=uuid4(), role=role)


def make_address(buyer_id, is_default: bool = False, address_id=None) -> AddressReadSchema:
    now = datetime.now(UTC)
    return AddressReadSchema(
        id=address_id or uuid4(),
        buyer_id=buyer_id,
        country='Russia',
        city='Moscow',
        street='Lenin str. 1',
        postal_code='101000',
        comment=None,
        is_default=is_default,
        created_at=now,
        updated_at=now,
    )


def create_request(is_default: bool = False) -> AddressCreateRequestSchema:
    return AddressCreateRequestSchema(
        country='Russia',
        city='Moscow',
        street='Lenin str. 1',
        postal_code='101000',
        is_default=is_default,
    )


@pytest.mark.anyio
async def test_create_address_uses_jwt_buyer_id():
    repo = FakeAddressRepository()
    user = make_user()
    use_case = CreateAddressUseCase(address_repository=repo)

    result = await use_case(create_request(), user)

    assert result.buyer_id == user.id
    assert repo.created[0].buyer_id == user.id


@pytest.mark.anyio
async def test_create_address_with_default_unsets_other_defaults():
    user = make_user()
    repo = FakeAddressRepository()
    existing_default = make_address(buyer_id=user.id, is_default=True)
    repo.add(existing_default)

    use_case = CreateAddressUseCase(address_repository=repo)

    await use_case(create_request(is_default=True), user)

    assert repo.default_unset_calls == [(user.id, None)]
    assert repo.by_id[existing_default.id].is_default is False


@pytest.mark.anyio
async def test_create_address_without_default_does_not_unset():
    user = make_user()
    repo = FakeAddressRepository()
    existing_default = make_address(buyer_id=user.id, is_default=True)
    repo.add(existing_default)

    use_case = CreateAddressUseCase(address_repository=repo)

    await use_case(create_request(is_default=False), user)

    assert repo.default_unset_calls == []
    assert repo.by_id[existing_default.id].is_default is True


@pytest.mark.anyio
async def test_list_addresses_only_returns_current_buyer_addresses():
    user = make_user()
    other = make_user()
    repo = FakeAddressRepository()
    own = make_address(buyer_id=user.id)
    foreign = make_address(buyer_id=other.id)
    repo.add(own)
    repo.add(foreign)

    use_case = ListAddressesUseCase(address_repository=repo)
    result = await use_case(user)

    assert [r.id for r in result] == [own.id]


@pytest.mark.anyio
async def test_update_address_rejects_foreign_buyer():
    user = make_user()
    other = make_user()
    repo = FakeAddressRepository()
    foreign = make_address(buyer_id=other.id)
    repo.add(foreign)

    use_case = UpdateAddressUseCase(address_repository=repo)

    with pytest.raises(AddressNotFoundError):
        await use_case(foreign.id, AddressUpdateRequestSchema(city='Other'), user)


@pytest.mark.anyio
async def test_update_address_sets_default_and_unsets_other_defaults():
    user = make_user()
    repo = FakeAddressRepository()
    other_default = make_address(buyer_id=user.id, is_default=True)
    target = make_address(buyer_id=user.id, is_default=False)
    repo.add(other_default)
    repo.add(target)

    use_case = UpdateAddressUseCase(address_repository=repo)
    result = await use_case(target.id, AddressUpdateRequestSchema(is_default=True), user)

    assert result.is_default is True
    assert repo.default_unset_calls == [(user.id, target.id)]
    assert repo.by_id[other_default.id].is_default is False


@pytest.mark.anyio
async def test_delete_address_rejects_foreign_buyer():
    user = make_user()
    other = make_user()
    repo = FakeAddressRepository()
    foreign = make_address(buyer_id=other.id)
    repo.add(foreign)

    use_case = DeleteAddressUseCase(address_repository=repo)

    with pytest.raises(AddressNotFoundError):
        await use_case(foreign.id, user)

    # Address must still exist
    assert foreign.id in repo.by_id


@pytest.mark.anyio
async def test_delete_address_removes_owned_address():
    user = make_user()
    repo = FakeAddressRepository()
    own = make_address(buyer_id=user.id)
    repo.add(own)

    use_case = DeleteAddressUseCase(address_repository=repo)
    await use_case(own.id, user)

    assert own.id not in repo.by_id
    assert repo.deleted == [own.id]
