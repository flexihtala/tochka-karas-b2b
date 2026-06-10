from uuid import uuid4

import pytest

from apps.blocking_reasons.errors import (
    BlockingReasonAlreadyExistsError,
    BlockingReasonNotFoundError,
    BlockingReasonReferencedError,
)
from apps.blocking_reasons.schemas.request import (
    BlockingReasonCreateRequestSchema,
    BlockingReasonUpdateRequestSchema,
)
from apps.blocking_reasons.use_cases.create import CreateBlockingReasonUseCase
from apps.blocking_reasons.use_cases.delete import DeleteBlockingReasonUseCase
from apps.blocking_reasons.use_cases.list import ListBlockingReasonsUseCase
from apps.blocking_reasons.use_cases.update import UpdateBlockingReasonUseCase
from tests.blocking_reasons.fakes import (
    FakeBlockingReasonRepository,
    FakeTicketReferenceRepository,
    make_blocking_reason,
)


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
async def test_list_returns_active_reasons():
    """DoD: без фильтра возвращаются только активные причины (is_active по умолчанию true)."""
    repo = FakeBlockingReasonRepository()
    active_soft = make_blocking_reason(code='REASON_B', title='Мягкая причина', hard_block=False, is_active=True)
    active_hard = make_blocking_reason(code='REASON_C', title='Жёсткая причина', hard_block=True, is_active=True)
    repo.add(active_soft)
    repo.add(active_hard)
    repo.add(make_blocking_reason(code='REASON_A', hard_block=True, is_active=False))
    use_case = ListBlockingReasonsUseCase(blocking_reason_repository=repo)

    result = await use_case()

    assert {i.code for i in result} == {'REASON_B', 'REASON_C'}
    by_id = {i.id: i for i in result}
    assert by_id[active_soft.id].title == 'Мягкая причина'
    assert by_id[active_soft.id].hard_block is False
    assert by_id[active_hard.id].title == 'Жёсткая причина'
    assert by_id[active_hard.id].hard_block is True


@pytest.mark.anyio
async def test_inactive_reasons_not_visible():
    """DoD: деактивированная причина не попадает в дефолтный список."""
    repo = FakeBlockingReasonRepository()
    reason = make_blocking_reason(code='DEACTIVATED', is_active=True)
    repo.add(reason)
    repo.add(make_blocking_reason(code='STILL_ACTIVE', is_active=True))
    use_case = ListBlockingReasonsUseCase(blocking_reason_repository=repo)

    # Деактивируем причину (как это делает PATCH is_active=false / DELETE).
    reason.is_active = False

    result = await use_case()

    assert {i.code for i in result} == {'STILL_ACTIVE'}
    assert reason.id not in {i.id for i in result}


@pytest.mark.anyio
async def test_list_blocking_reasons_explicit_inactive_filter_returns_only_inactive():
    """?is_active=false (admin-сценарий) явно показывает деактивированные причины."""
    repo = FakeBlockingReasonRepository()
    repo.add(make_blocking_reason(code='ACTIVE', is_active=True))
    repo.add(make_blocking_reason(code='INACTIVE', is_active=False))
    use_case = ListBlockingReasonsUseCase(blocking_reason_repository=repo)

    result = await use_case(is_active=False)

    assert {i.code for i in result} == {'INACTIVE'}


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
    ticket_repo = FakeTicketReferenceRepository()
    use_case = DeleteBlockingReasonUseCase(blocking_reason_repository=repo, ticket_repository=ticket_repo)

    await use_case(reason.id)

    assert repo.by_id[reason.id].is_active is False
    assert ticket_repo.calls == [reason.id]


@pytest.mark.anyio
async def test_referenced_reason_cannot_be_deleted():
    """DoD: причина, на которую ссылается карточка модерации, не удаляется — 409, остаётся активной."""
    repo = FakeBlockingReasonRepository()
    reason = make_blocking_reason(code='REFERENCED', is_active=True)
    repo.add(reason)
    ticket_repo = FakeTicketReferenceRepository(referenced_reason_ids={reason.id})
    use_case = DeleteBlockingReasonUseCase(blocking_reason_repository=repo, ticket_repository=ticket_repo)

    with pytest.raises(BlockingReasonReferencedError) as exc_info:
        await use_case(reason.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == 'BLOCKING_REASON_REFERENCED'
    assert repo.by_id[reason.id].is_active is True
    assert repo.updated == []


@pytest.mark.anyio
async def test_delete_blocking_reason_404_when_missing():
    use_case = DeleteBlockingReasonUseCase(
        blocking_reason_repository=FakeBlockingReasonRepository(),
        ticket_repository=FakeTicketReferenceRepository(),
    )

    with pytest.raises(BlockingReasonNotFoundError):
        await use_case(uuid4())
