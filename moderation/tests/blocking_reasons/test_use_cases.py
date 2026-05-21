from uuid import uuid4

import pytest

from apps.blocking_reasons.errors import (
    BlockingReasonAlreadyExistsError,
    BlockingReasonNotFoundError,
)
from apps.blocking_reasons.schemas.request import (
    BlockingReasonCreateRequestSchema,
    BlockingReasonUpdateRequestSchema,
)
from apps.blocking_reasons.use_cases.create import CreateBlockingReasonUseCase
from apps.blocking_reasons.use_cases.delete import DeleteBlockingReasonUseCase
from apps.blocking_reasons.use_cases.list import ListBlockingReasonsUseCase
from apps.blocking_reasons.use_cases.update import UpdateBlockingReasonUseCase
from tests.blocking_reasons.fakes import FakeBlockingReasonRepository, make_blocking_reason


@pytest.mark.anyio
async def test_create_blocking_reason_persists_and_returns_response():
    repo = FakeBlockingReasonRepository()
    use_case = CreateBlockingReasonUseCase(blocking_reason_repository=repo)

    result = await use_case(
        BlockingReasonCreateRequestSchema(
            code='FORBIDDEN_GOODS',
            title='Запрещённые товары',
            description='Оружие, наркотики и т.д.',
            hard_block=True,
        ),
    )

    assert result.code == 'FORBIDDEN_GOODS'
    assert result.title == 'Запрещённые товары'
    assert result.hard_block is True
    assert result.is_active is True
    assert repo.created[0].code == 'FORBIDDEN_GOODS'
    assert repo.created[0].title == 'Запрещённые товары'


@pytest.mark.anyio
async def test_create_blocking_reason_rejects_duplicate_code():
    repo = FakeBlockingReasonRepository()
    repo.add(make_blocking_reason(code='DUP'))
    use_case = CreateBlockingReasonUseCase(blocking_reason_repository=repo)

    with pytest.raises(BlockingReasonAlreadyExistsError):
        await use_case(BlockingReasonCreateRequestSchema(code='DUP', title='dup', hard_block=False))


@pytest.mark.anyio
async def test_list_blocking_reasons_returns_all_when_no_filters():
    repo = FakeBlockingReasonRepository()
    repo.add(make_blocking_reason(code='REASON_B', hard_block=False, is_active=True))
    repo.add(make_blocking_reason(code='REASON_A', hard_block=True, is_active=False))
    use_case = ListBlockingReasonsUseCase(blocking_reason_repository=repo)

    result = await use_case()

    assert len(result) == 2
    assert {i.code for i in result} == {'REASON_A', 'REASON_B'}


@pytest.mark.anyio
async def test_list_blocking_reasons_filters_by_hard_block_and_active():
    repo = FakeBlockingReasonRepository()
    repo.add(make_blocking_reason(code='HARD_ACTIVE', hard_block=True, is_active=True))
    repo.add(make_blocking_reason(code='SOFT_ACTIVE', hard_block=False, is_active=True))
    repo.add(make_blocking_reason(code='HARD_INACTIVE', hard_block=True, is_active=False))
    use_case = ListBlockingReasonsUseCase(blocking_reason_repository=repo)

    result = await use_case(hard_block=True, is_active=True)

    assert len(result) == 1
    assert result[0].code == 'HARD_ACTIVE'


@pytest.mark.anyio
async def test_update_blocking_reason_applies_partial_update():
    repo = FakeBlockingReasonRepository()
    reason = make_blocking_reason(code='OLD', title='Old', description='old desc')
    repo.add(reason)
    use_case = UpdateBlockingReasonUseCase(blocking_reason_repository=repo)

    result = await use_case(
        reason.id,
        BlockingReasonUpdateRequestSchema(description='new desc', title='Renamed'),
    )

    assert result.description == 'new desc'
    assert result.title == 'Renamed'
    # code не меняется через PATCH (по спеке).
    assert result.code == 'OLD'


@pytest.mark.anyio
async def test_update_blocking_reason_404_when_missing():
    use_case = UpdateBlockingReasonUseCase(blocking_reason_repository=FakeBlockingReasonRepository())

    with pytest.raises(BlockingReasonNotFoundError):
        await use_case(uuid4(), BlockingReasonUpdateRequestSchema(description='x'))


@pytest.mark.anyio
async def test_delete_blocking_reason_marks_inactive():
    repo = FakeBlockingReasonRepository()
    reason = make_blocking_reason(code='TO_DELETE', is_active=True)
    repo.add(reason)
    use_case = DeleteBlockingReasonUseCase(blocking_reason_repository=repo)

    await use_case(reason.id)

    assert repo.by_id[reason.id].is_active is False


@pytest.mark.anyio
async def test_delete_blocking_reason_404_when_missing():
    use_case = DeleteBlockingReasonUseCase(blocking_reason_repository=FakeBlockingReasonRepository())

    with pytest.raises(BlockingReasonNotFoundError):
        await use_case(uuid4())
