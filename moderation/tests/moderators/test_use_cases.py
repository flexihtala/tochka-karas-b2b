from uuid import uuid4

import pytest

from apps.moderators.errors import EmailAlreadyExistsError, ModeratorNotFoundError
from apps.moderators.schemas.request import ModeratorCreateRequestSchema, ModeratorUpdateRequestSchema
from apps.moderators.use_cases.create_moderator import CreateModeratorUseCase
from apps.moderators.use_cases.get_moderator import GetModeratorUseCase
from apps.moderators.use_cases.list_moderators import ListModeratorsUseCase
from apps.moderators.use_cases.update_moderator import UpdateModeratorUseCase
from shared.auth_lib import UserRole
from tests.moderators.fakes import FakeModeratorRepository, FakePasswordHasher, make_moderator_read_schema


def create_request(email: str = 'new-mod@example.com') -> ModeratorCreateRequestSchema:
    return ModeratorCreateRequestSchema(
        email=email,
        password='SecurePass123!',
        first_name='Анна',
        last_name='Сидорова',
        role=UserRole.MODERATOR,
    )


@pytest.mark.anyio
async def test_create_moderator_persists_and_returns_response():
    moderators = FakeModeratorRepository()

    use_case = CreateModeratorUseCase(
        moderator_repository=moderators,
        password_hasher=FakePasswordHasher(),
    )

    result = await use_case(create_request())

    assert result.email == 'new-mod@example.com'
    assert result.role == UserRole.MODERATOR
    assert result.is_active is True
    assert moderators.created[0].password_hash == 'hashed:SecurePass123!'
    # Гарантируем, что password_hash не утекает через response-схему.
    assert 'password_hash' not in result.model_dump()


@pytest.mark.anyio
async def test_create_moderator_rejects_duplicate_email():
    moderators = FakeModeratorRepository()
    moderators.add(make_moderator_read_schema(email='dup@example.com'))

    use_case = CreateModeratorUseCase(
        moderator_repository=moderators,
        password_hasher=FakePasswordHasher(),
    )

    with pytest.raises(EmailAlreadyExistsError):
        await use_case(create_request(email='dup@example.com'))


@pytest.mark.anyio
async def test_get_moderator_returns_existing():
    moderators = FakeModeratorRepository()
    moderator = make_moderator_read_schema(email='mod@example.com')
    moderators.add(moderator)

    use_case = GetModeratorUseCase(moderator_repository=moderators)

    result = await use_case(moderator.id)

    assert result.id == moderator.id
    assert result.email == 'mod@example.com'


@pytest.mark.anyio
async def test_get_moderator_returns_404_for_missing():
    use_case = GetModeratorUseCase(moderator_repository=FakeModeratorRepository())

    with pytest.raises(ModeratorNotFoundError):
        await use_case(uuid4())


@pytest.mark.anyio
async def test_list_moderators_paginates_and_filters():
    moderators = FakeModeratorRepository()
    moderators.add(make_moderator_read_schema(email='a@example.com', is_active=True))
    moderators.add(make_moderator_read_schema(email='b@example.com', is_active=False))
    moderators.add(make_moderator_read_schema(email='c@example.com', is_active=True))

    use_case = ListModeratorsUseCase(moderator_repository=moderators)

    all_result = await use_case(limit=10, offset=0)
    assert all_result.total_count == 3
    assert len(all_result.items) == 3
    assert all_result.limit == 10
    assert all_result.offset == 0

    active_result = await use_case(limit=10, offset=0, is_active=True)
    assert active_result.total_count == 2
    assert {m.email for m in active_result.items} == {'a@example.com', 'c@example.com'}


@pytest.mark.anyio
async def test_update_moderator_applies_partial_update():
    moderators = FakeModeratorRepository()
    moderator = make_moderator_read_schema(email='mod@example.com', is_active=True)
    moderators.add(moderator)

    use_case = UpdateModeratorUseCase(moderator_repository=moderators)

    result = await use_case(
        moderator.id,
        ModeratorUpdateRequestSchema(first_name='Пётр', is_active=False),
    )

    assert result.first_name == 'Пётр'
    assert result.is_active is False
    assert moderators.updated[0].first_name == 'Пётр'
    assert moderators.updated[0].is_active is False


@pytest.mark.anyio
async def test_update_moderator_404_when_missing():
    use_case = UpdateModeratorUseCase(moderator_repository=FakeModeratorRepository())

    with pytest.raises(ModeratorNotFoundError):
        await use_case(uuid4(), ModeratorUpdateRequestSchema(first_name='X'))


@pytest.mark.anyio
async def test_update_moderator_with_empty_payload_is_noop():
    moderators = FakeModeratorRepository()
    moderator = make_moderator_read_schema(email='mod@example.com', first_name='Ivan')
    moderators.add(moderator)

    use_case = UpdateModeratorUseCase(moderator_repository=moderators)

    result = await use_case(moderator.id, ModeratorUpdateRequestSchema())

    assert result.first_name == 'Ivan'
    assert moderators.updated == []
