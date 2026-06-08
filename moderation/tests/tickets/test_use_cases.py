from uuid import uuid4

import pytest

from apps.blocking_reasons.errors import BlockingReasonNotFoundError
from apps.tickets.enums import TicketStatus
from apps.tickets.errors import (
    TicketNoSkusError,
    TicketNotAssignedError,
    TicketNotFoundError,
    TicketNotOwnerError,
    TicketTerminalError,
    TicketWrongStatusError,
)
from apps.tickets.schemas.request import BlockTicketRequestSchema, FieldReportSchema
from apps.tickets.use_cases.approve_ticket import ApproveTicketUseCase
from apps.tickets.use_cases.block_ticket import BlockTicketUseCase
from apps.tickets.use_cases.release_ticket import ReleaseTicketUseCase
from shared.auth_lib import UserRole
from tests.blocking_reasons.fakes import FakeBlockingReasonRepository, make_blocking_reason
from tests.tickets.fakes import (
    FakeModerationB2BClient,
    FakeOutboxRepository,
    FakeSessionManager,
    FakeTicketRepository,
    make_ticket,
)


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
async def test_approve_transitions_to_moderated_and_emits_event():
    """Happy path: тикет IN_REVIEW, владелец-модератор, у товара в B2B есть SKU →
    статус APPROVED + ровно одно outbox-событие MODERATED для b2b с product_id."""
    repo = FakeTicketRepository()
    outbox = FakeOutboxRepository()
    b2b = FakeModerationB2BClient(product={'skus': [{'id': str(uuid4())}]})
    moderator_id = uuid4()
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=moderator_id)
    repo.add(ticket)
    use_case = ApproveTicketUseCase(
        ticket_repository=repo,
        outbox_repository=outbox,
        b2b_client=b2b,
        session_manager=FakeSessionManager(),
    )

    result = await use_case(ticket.id, moderator_id, UserRole.MODERATOR)

    assert result.status == TicketStatus.APPROVED
    assert result.decision_at is not None
    assert repo.by_id[ticket.id].status == TicketStatus.APPROVED
    # B2B was consulted for the product (SKU precondition).
    assert b2b.calls == [ticket.product_id]
    # Outbox enqueued exactly one MODERATED event for b2b.
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'MODERATED'
    assert event.target_service.value == 'b2b'
    assert event.payload['product_id'] == str(ticket.product_id)
    assert 'idempotency_key' in event.payload


@pytest.mark.anyio
async def test_approve_others_card_returns_403():
    """Тикет захвачен ДРУГИМ модератором, вызывающий не ADMIN → 403
    (TicketNotOwnerError). B2B не дёргается, outbox пуст."""
    repo = FakeTicketRepository()
    outbox = FakeOutboxRepository()
    b2b = FakeModerationB2BClient()
    owner_id = uuid4()
    other_moderator = uuid4()
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=owner_id)
    repo.add(ticket)
    use_case = ApproveTicketUseCase(
        ticket_repository=repo,
        outbox_repository=outbox,
        b2b_client=b2b,
        session_manager=FakeSessionManager(),
    )

    with pytest.raises(TicketNotOwnerError) as err:
        await use_case(ticket.id, other_moderator, UserRole.MODERATOR)

    assert err.value.status_code == 403
    assert b2b.calls == []
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_approve_after_edited_returns_409():
    """Тикет был IN_REVIEW, но продавец отредактировал карточку → тикет сброшен в
    PENDING (claimed_by=None). approve по устаревшему review → 409, outbox пуст.

    Сам сброс IN_REVIEW → PENDING выполняет обработчик ВХОДЯЩИХ B2B-событий
    (отдельный квест модерации, вне скоупа US-MOD-03): seller-edit прилетает
    событием, хендлер un-claim'ит тикет. Здесь мы лишь моделируем итоговое
    состояние и проверяем, что approve корректно отвергает протухший review
    существующей проверкой status != IN_REVIEW.
    """
    repo = FakeTicketRepository()
    outbox = FakeOutboxRepository()
    b2b = FakeModerationB2BClient()
    moderator_id = uuid4()
    # Был IN_REVIEW у модератора → seller-edit сбросил в PENDING и снял claim.
    ticket = make_ticket(status=TicketStatus.PENDING, claimed_by=None)
    repo.add(ticket)
    use_case = ApproveTicketUseCase(
        ticket_repository=repo,
        outbox_repository=outbox,
        b2b_client=b2b,
        session_manager=FakeSessionManager(),
    )

    with pytest.raises(TicketWrongStatusError) as err:
        await use_case(ticket.id, moderator_id, UserRole.MODERATOR)

    assert err.value.status_code == 409
    assert b2b.calls == []
    assert outbox.enqueued == []


@pytest.mark.anyio
async def test_approve_without_sku_returns_409():
    """Тикет IN_REVIEW, владелец-модератор, но у товара в B2B нет SKU
    (skus: []) → 409 (TicketNoSkusError). Статус не меняется, outbox пуст."""
    repo = FakeTicketRepository()
    outbox = FakeOutboxRepository()
    b2b = FakeModerationB2BClient(product={'skus': []})
    moderator_id = uuid4()
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=moderator_id)
    repo.add(ticket)
    use_case = ApproveTicketUseCase(
        ticket_repository=repo,
        outbox_repository=outbox,
        b2b_client=b2b,
        session_manager=FakeSessionManager(),
    )

    with pytest.raises(TicketNoSkusError) as err:
        await use_case(ticket.id, moderator_id, UserRole.MODERATOR)

    assert err.value.status_code == 409
    assert err.value.code == 'PRODUCT_HAS_NO_SKUS'
    # B2B was consulted, but ticket stays IN_REVIEW and no event is emitted.
    assert b2b.calls == [ticket.product_id]
    assert repo.by_id[ticket.id].status == TicketStatus.IN_REVIEW
    assert outbox.enqueued == []


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
    # B2B-контракт знает только event_type BLOCKED|MODERATED — жёсткость в отдельном
    # булевом hard_block. Поэтому даже hard block эмитит event_type='BLOCKED'.
    assert outbox.enqueued[0].event_type == 'BLOCKED'
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


# --------------------- US-MOD-05: HARD BLOCK (terminal) ---------------------


@pytest.mark.anyio
async def test_hard_block_transitions_to_terminal_and_emits_event():
    """DoD US-MOD-05: block с hard_block=true причиной → тикет HARD_BLOCKED (терминальный),
    ровно одна outbox-строка event_type='BLOCKED' для b2b с payload['hard_block'] is True."""
    repo = FakeTicketRepository()
    reasons = FakeBlockingReasonRepository()
    outbox = FakeOutboxRepository()
    moderator_id = uuid4()

    hard_reason = make_blocking_reason(title='Контрафактный товар', hard_block=True)
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
        BlockTicketRequestSchema(blocking_reason_ids=[hard_reason.id], comment='Контрафакт'),
        moderator_id,
        UserRole.MODERATOR,
    )

    # Терминальный статус HARD_BLOCKED и в ответе, и в persisted state.
    assert result.status == TicketStatus.HARD_BLOCKED
    assert repo.by_id[ticket.id].status == TicketStatus.HARD_BLOCKED
    # Ровно одно событие для b2b с event_type=BLOCKED и hard_block=True.
    assert len(outbox.enqueued) == 1
    event = outbox.enqueued[0]
    assert event.event_type == 'BLOCKED'
    assert event.target_service.value == 'b2b'
    assert event.payload['hard_block'] is True


@pytest.mark.anyio
async def test_hard_block_event_carries_hard_block_true():
    """DoD US-MOD-05: эмитированное событие несёт payload['hard_block'] == True
    (и event_type == 'BLOCKED', т.к. B2B-контракт не знает HARD_BLOCKED)."""
    repo = FakeTicketRepository()
    reasons = FakeBlockingReasonRepository()
    outbox = FakeOutboxRepository()
    moderator_id = uuid4()

    hard_reason = make_blocking_reason(title='Запрещён к продаже', hard_block=True)
    reasons.add(hard_reason)
    ticket = make_ticket(status=TicketStatus.IN_REVIEW, claimed_by=moderator_id)
    repo.add(ticket)

    use_case = BlockTicketUseCase(
        ticket_repository=repo,
        blocking_reason_repository=reasons,
        outbox_repository=outbox,
        session_manager=FakeSessionManager(),
    )

    await use_case(
        ticket.id,
        BlockTicketRequestSchema(blocking_reason_ids=[hard_reason.id]),
        moderator_id,
        UserRole.MODERATOR,
    )

    event = outbox.enqueued[0]
    assert event.event_type == 'BLOCKED'
    assert event.payload['hard_block'] == True  # noqa: E712 — DoD: явное сравнение с True


@pytest.mark.anyio
async def test_any_modify_on_hard_blocked_returns_403():
    """DoD US-MOD-05: над HARD_BLOCKED-тикетом approve/block/release каждый поднимает
    TicketTerminalError (403); ни одна outbox-строка не пишется."""
    moderator_id = uuid4()

    # ----- APPROVE -----
    approve_repo = FakeTicketRepository()
    approve_outbox = FakeOutboxRepository()
    b2b = FakeModerationB2BClient()
    approve_ticket = make_ticket(status=TicketStatus.HARD_BLOCKED, claimed_by=moderator_id)
    approve_repo.add(approve_ticket)
    approve_uc = ApproveTicketUseCase(
        ticket_repository=approve_repo,
        outbox_repository=approve_outbox,
        b2b_client=b2b,
        session_manager=FakeSessionManager(),
    )
    with pytest.raises(TicketTerminalError) as approve_err:
        await approve_uc(approve_ticket.id, moderator_id, UserRole.MODERATOR)
    assert approve_err.value.status_code == 403
    # B2B не дёргается, outbox пуст.
    assert b2b.calls == []
    assert approve_outbox.enqueued == []

    # ----- BLOCK -----
    block_repo = FakeTicketRepository()
    block_outbox = FakeOutboxRepository()
    reasons = FakeBlockingReasonRepository()
    reason = make_blocking_reason(hard_block=True)
    reasons.add(reason)
    block_ticket = make_ticket(status=TicketStatus.HARD_BLOCKED, claimed_by=moderator_id)
    block_repo.add(block_ticket)
    block_uc = BlockTicketUseCase(
        ticket_repository=block_repo,
        blocking_reason_repository=reasons,
        outbox_repository=block_outbox,
        session_manager=FakeSessionManager(),
    )
    with pytest.raises(TicketTerminalError) as block_err:
        await block_uc(
            block_ticket.id,
            BlockTicketRequestSchema(blocking_reason_ids=[reason.id]),
            moderator_id,
            UserRole.MODERATOR,
        )
    assert block_err.value.status_code == 403
    assert block_outbox.enqueued == []

    # ----- RELEASE -----
    release_repo = FakeTicketRepository()
    release_ticket = make_ticket(status=TicketStatus.HARD_BLOCKED, claimed_by=moderator_id)
    release_repo.add(release_ticket)
    release_uc = ReleaseTicketUseCase(ticket_repository=release_repo)
    with pytest.raises(TicketTerminalError) as release_err:
        await release_uc(release_ticket.id, moderator_id, UserRole.MODERATOR)
    assert release_err.value.status_code == 403
