from uuid import uuid4

import pytest

from apps.blocking_reasons.errors import BlockingReasonNotFoundError
from apps.tickets.enums import TicketStatus
from apps.tickets.errors import TicketNotAssignedError, TicketNotFoundError, TicketWrongStatusError
from apps.tickets.schemas.request import BlockTicketRequestSchema, FieldReportSchema
from apps.tickets.use_cases.approve_ticket import ApproveTicketUseCase
from apps.tickets.use_cases.block_ticket import BlockTicketUseCase
from apps.tickets.use_cases.release_ticket import ReleaseTicketUseCase
from shared.auth_lib import UserRole
from tests.blocking_reasons.fakes import FakeBlockingReasonRepository, make_blocking_reason
from tests.tickets.fakes import FakeOutboxRepository, FakeSessionManager, FakeTicketRepository, make_ticket


# ----------------------------- RELEASE -----------------------------


@pytest.mark.anyio
async def test_release_returns_pending_and_clears_claim():
    repo = FakeTicketRepository()
    moderator_id = uuid4()
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=moderator_id)
    repo.add(ticket)
    use_case = ReleaseTicketUseCase(ticket_repository=repo)

    result = await use_case(ticket.id, moderator_id, UserRole.MODERATOR)

    assert result.status == TicketStatus.PENDING
    assert result.assigned_moderator_id is None
    assert result.claimed_at is None
    assert repo.by_id[ticket.id].status == TicketStatus.PENDING
    assert repo.by_id[ticket.id].claimed_by is None


@pytest.mark.anyio
async def test_release_rejects_when_not_owner_and_not_admin():
    repo = FakeTicketRepository()
    owner_id = uuid4()
    other_moderator = uuid4()
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=owner_id)
    repo.add(ticket)
    use_case = ReleaseTicketUseCase(ticket_repository=repo)

    with pytest.raises(TicketNotAssignedError):
        await use_case(ticket.id, other_moderator, UserRole.MODERATOR)


@pytest.mark.anyio
async def test_release_allows_admin_to_release_others_ticket():
    repo = FakeTicketRepository()
    owner_id = uuid4()
    admin_id = uuid4()
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=owner_id)
    repo.add(ticket)
    use_case = ReleaseTicketUseCase(ticket_repository=repo)

    result = await use_case(ticket.id, admin_id, UserRole.ADMIN)

    assert result.status == TicketStatus.PENDING


@pytest.mark.anyio
async def test_release_404_when_missing():
    use_case = ReleaseTicketUseCase(ticket_repository=FakeTicketRepository())

    with pytest.raises(TicketNotFoundError):
        await use_case(uuid4(), uuid4(), UserRole.MODERATOR)


@pytest.mark.anyio
async def test_release_409_when_wrong_status():
    repo = FakeTicketRepository()
    moderator_id = uuid4()
    ticket = make_ticket(status=TicketStatus.PENDING, claimed_by=moderator_id)
    repo.add(ticket)
    use_case = ReleaseTicketUseCase(ticket_repository=repo)

    with pytest.raises(TicketWrongStatusError):
        await use_case(ticket.id, moderator_id, UserRole.MODERATOR)


# ----------------------------- APPROVE -----------------------------


@pytest.mark.anyio
async def test_approve_marks_approved_and_enqueues_moderated_event():
    repo = FakeTicketRepository()
    outbox = FakeOutboxRepository()
    moderator_id = uuid4()
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=moderator_id)
    repo.add(ticket)
    use_case = ApproveTicketUseCase(
        ticket_repository=repo,
        outbox_repository=outbox,
        session_manager=FakeSessionManager(),
    )

    result = await use_case(ticket.id, moderator_id, UserRole.MODERATOR)

    assert result.status == TicketStatus.APPROVED
    assert result.decision_at is not None
    assert repo.by_id[ticket.id].status == TicketStatus.APPROVED
    # Outbox enqueued exactly one MODERATED event for b2b.
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'MODERATED'
    assert event.target_service.value == 'b2b'
    assert event.payload['product_id'] == str(ticket.product_id)
    assert 'idempotency_key' in event.payload


@pytest.mark.anyio
async def test_approve_rejects_when_not_owner_and_not_admin():
    repo = FakeTicketRepository()
    owner_id = uuid4()
    other_moderator = uuid4()
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=owner_id)
    repo.add(ticket)
    use_case = ApproveTicketUseCase(
        ticket_repository=repo,
        outbox_repository=FakeOutboxRepository(),
        session_manager=FakeSessionManager(),
    )

    with pytest.raises(TicketNotAssignedError):
        await use_case(ticket.id, other_moderator, UserRole.MODERATOR)


@pytest.mark.anyio
async def test_approve_409_when_status_not_in_review():
    repo = FakeTicketRepository()
    moderator_id = uuid4()
    ticket = make_ticket(status=TicketStatus.PENDING, claimed_by=moderator_id)
    repo.add(ticket)
    use_case = ApproveTicketUseCase(
        ticket_repository=repo,
        outbox_repository=FakeOutboxRepository(),
        session_manager=FakeSessionManager(),
    )

    with pytest.raises(TicketWrongStatusError):
        await use_case(ticket.id, moderator_id, UserRole.MODERATOR)


# ----------------------------- BLOCK -----------------------------


@pytest.mark.anyio
async def test_block_soft_emits_event_with_hard_block_false():
    repo = FakeTicketRepository()
    reasons = FakeBlockingReasonRepository()
    outbox = FakeOutboxRepository()
    moderator_id = uuid4()

    soft_reason = make_blocking_reason(title='Soft', hard_block=False)
    reasons.add(soft_reason)
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=moderator_id)
    repo.add(ticket)

    use_case = BlockTicketUseCase(
        ticket_repository=repo,
        blocking_reason_repository=reasons,
        outbox_repository=outbox,
        session_manager=FakeSessionManager(),
    )

    result = await use_case(
        ticket.id,
        BlockTicketRequestSchema(
            blocking_reason_ids=[soft_reason.id],
            comment='Описание не соответствует',
            field_reports=[
                FieldReportSchema(field_path='description', message='Скопировано'),
            ],
        ),
        moderator_id,
        UserRole.MODERATOR,
    )

    assert result.status == TicketStatus.BLOCKED
    # Спека TicketResponse не отдаёт blocking_reason_id напрямую — он живёт в DB
    # и в outbox payload. Поверяем persisted state в репозитории.
    assert repo.by_id[ticket.id].blocking_reason_id == soft_reason.id
    # comment персистится в БД (read-schema), но не утекает в response (см. response.py).
    assert repo.by_id[ticket.id].moderator_comment == 'Описание не соответствует'
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'BLOCKED'
    assert event.payload['hard_block'] is False
    assert event.payload['blocking_reason_ids'] == [str(soft_reason.id)]
    assert event.payload['comment'] == 'Описание не соответствует'
    assert event.payload['field_reports'] == [
        {'field_path': 'description', 'message': 'Скопировано', 'severity': 'ERROR'}
    ]


@pytest.mark.anyio
async def test_block_hard_emits_hard_blocked_event_and_status():
    repo = FakeTicketRepository()
    reasons = FakeBlockingReasonRepository()
    outbox = FakeOutboxRepository()
    moderator_id = uuid4()

    hard_reason = make_blocking_reason(title='Forbidden', hard_block=True)
    reasons.add(hard_reason)
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=moderator_id)
    repo.add(ticket)

    use_case = BlockTicketUseCase(
        ticket_repository=repo,
        blocking_reason_repository=reasons,
        outbox_repository=outbox,
        session_manager=FakeSessionManager(),
    )

    result = await use_case(
        ticket.id,
        BlockTicketRequestSchema(
            blocking_reason_ids=[hard_reason.id],
            comment='Запрещённый товар',
        ),
        moderator_id,
        UserRole.MODERATOR,
    )

    # По спеке hard_block=true → терминальный статус HARD_BLOCKED.
    assert result.status == TicketStatus.HARD_BLOCKED
    assert outbox.enqueued[0].event_type == 'HARD_BLOCKED'
    assert outbox.enqueued[0].payload['hard_block'] is True


@pytest.mark.anyio
async def test_block_404_when_reason_not_found():
    repo = FakeTicketRepository()
    moderator_id = uuid4()
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=moderator_id)
    repo.add(ticket)
    use_case = BlockTicketUseCase(
        ticket_repository=repo,
        blocking_reason_repository=FakeBlockingReasonRepository(),
        outbox_repository=FakeOutboxRepository(),
        session_manager=FakeSessionManager(),
    )

    with pytest.raises(BlockingReasonNotFoundError):
        await use_case(
            ticket.id,
            BlockTicketRequestSchema(blocking_reason_ids=[uuid4()], comment='x'),
            moderator_id,
            UserRole.MODERATOR,
        )


@pytest.mark.anyio
async def test_block_rejects_inactive_reason():
    repo = FakeTicketRepository()
    reasons = FakeBlockingReasonRepository()
    moderator_id = uuid4()
    inactive_reason = make_blocking_reason(title='Old', is_active=False)
    reasons.add(inactive_reason)
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=moderator_id)
    repo.add(ticket)
    use_case = BlockTicketUseCase(
        ticket_repository=repo,
        blocking_reason_repository=reasons,
        outbox_repository=FakeOutboxRepository(),
        session_manager=FakeSessionManager(),
    )

    with pytest.raises(BlockingReasonNotFoundError):
        await use_case(
            ticket.id,
            BlockTicketRequestSchema(blocking_reason_ids=[inactive_reason.id], comment='x'),
            moderator_id,
            UserRole.MODERATOR,
        )


@pytest.mark.anyio
async def test_block_rejects_when_not_owner_and_not_admin():
    repo = FakeTicketRepository()
    reasons = FakeBlockingReasonRepository()
    owner_id = uuid4()
    other_moderator = uuid4()
    reason = make_blocking_reason()
    reasons.add(reason)
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=owner_id)
    repo.add(ticket)
    use_case = BlockTicketUseCase(
        ticket_repository=repo,
        blocking_reason_repository=reasons,
        outbox_repository=FakeOutboxRepository(),
        session_manager=FakeSessionManager(),
    )

    with pytest.raises(TicketNotAssignedError):
        await use_case(
            ticket.id,
            BlockTicketRequestSchema(blocking_reason_ids=[reason.id], comment='x'),
            other_moderator,
            UserRole.MODERATOR,
        )


@pytest.mark.anyio
async def test_block_multiple_reasons_any_hard_makes_hard_blocked():
    """blocking_reason_ids — массив; если хотя бы одна причина hard_block — HARD_BLOCKED."""
    repo = FakeTicketRepository()
    reasons = FakeBlockingReasonRepository()
    outbox = FakeOutboxRepository()
    moderator_id = uuid4()

    soft = make_blocking_reason(title='Soft', hard_block=False)
    hard = make_blocking_reason(title='Hard', hard_block=True)
    reasons.add(soft)
    reasons.add(hard)
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=moderator_id)
    repo.add(ticket)

    use_case = BlockTicketUseCase(
        ticket_repository=repo,
        blocking_reason_repository=reasons,
        outbox_repository=outbox,
        session_manager=FakeSessionManager(),
    )

    result = await use_case(
        ticket.id,
        BlockTicketRequestSchema(blocking_reason_ids=[soft.id, hard.id]),
        moderator_id,
        UserRole.MODERATOR,
    )

    assert result.status == TicketStatus.HARD_BLOCKED
    assert outbox.enqueued[0].payload['blocking_reason_ids'] == [str(soft.id), str(hard.id)]
