from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from apps.tickets.enums import TicketKind, TicketStatus
from apps.tickets.schemas.db import TicketCreateSchema, TicketReadSchema, TicketUpdateSchema
from shared.outbox import OutboxEnqueueSchema


def make_ticket(
    *,
    id: UUID | None = None,
    product_id: UUID | None = None,
    seller_id: UUID | None = None,
    category_id: UUID | None = None,
    kind: TicketKind = TicketKind.CREATE,
    status: TicketStatus = TicketStatus.PENDING,
    queue_priority: int = 3,
    claimed_by: UUID | None = None,
    claimed_at: datetime | None = None,
    claim_expires_at: datetime | None = None,
    decision_at: datetime | None = None,
    blocking_reason_id: UUID | None = None,
    moderator_comment: str | None = None,
    field_reports: list[dict[str, Any]] | None = None,
    json_before: dict[str, Any] | None = None,
    json_after: dict[str, Any] | None = None,
) -> TicketReadSchema:
    now = datetime.now(UTC)
    return TicketReadSchema(
        id=id or uuid4(),
        product_id=product_id or uuid4(),
        seller_id=seller_id or uuid4(),
        category_id=category_id,
        kind=kind,
        status=status,
        queue_priority=queue_priority,
        claimed_by=claimed_by,
        claimed_at=claimed_at,
        claim_expires_at=claim_expires_at,
        decision_at=decision_at,
        blocking_reason_id=blocking_reason_id,
        moderator_comment=moderator_comment,
        field_reports=field_reports if field_reports is not None else [],
        json_before=json_before,
        json_after=json_after or {},
        created_at=now,
        updated_at=now,
    )


class FakeTicketRepository:
    """Fake-репозиторий, реализующий публичный контракт TicketRepository.

    `claim_next()` имитирует SELECT FOR UPDATE SKIP LOCKED — в продакшне это делает
    реальный SQL, в тестах достаточно проверить что use-case вызывает именно этот
    метод (а не ходит мимо абстракции).
    """

    def __init__(self):
        self.by_id: dict[UUID, TicketReadSchema] = {}
        self.created: list[TicketCreateSchema] = []
        self.updated: list[TicketUpdateSchema] = []
        self.claim_next_calls: list[UUID] = []

    def add(self, ticket: TicketReadSchema) -> None:
        self.by_id[ticket.id] = ticket

    async def create(self, data: TicketCreateSchema) -> TicketReadSchema:
        self.created.append(data)
        ticket = make_ticket(
            id=data.id or uuid4(),
            product_id=data.product_id,
            seller_id=data.seller_id,
            category_id=data.category_id,
            kind=data.kind,
            status=data.status,
            queue_priority=data.queue_priority,
            claimed_by=data.claimed_by,
            claimed_at=data.claimed_at,
            claim_expires_at=data.claim_expires_at,
            decision_at=data.decision_at,
            blocking_reason_id=data.blocking_reason_id,
            moderator_comment=data.moderator_comment,
            field_reports=data.field_reports,
            json_before=data.json_before,
            json_after=data.json_after,
        )
        self.add(ticket)
        return ticket

    async def get_or_none(self, id_: UUID) -> TicketReadSchema | None:
        return self.by_id.get(id_)

    async def update(self, data: TicketUpdateSchema) -> TicketReadSchema | None:
        existing = self.by_id.get(data.id)
        if existing is None:
            return None
        self.updated.append(data)
        update_payload = data.model_dump(exclude_unset=True, exclude={'id'})
        for key, value in update_payload.items():
            setattr(existing, key, value)
        self.by_id[data.id] = existing
        return existing

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        status: TicketStatus | None = None,
        queue_priority: int | None = None,
        category_id: UUID | None = None,
        seller_id: UUID | None = None,
    ) -> tuple[list[TicketReadSchema], int]:
        items = list(self.by_id.values())
        if status is not None:
            items = [t for t in items if t.status == status]
        if queue_priority is not None:
            items = [t for t in items if t.queue_priority == queue_priority]
        if category_id is not None:
            items = [t for t in items if getattr(t, 'category_id', None) == category_id]
        if seller_id is not None:
            items = [t for t in items if t.seller_id == seller_id]
        total_count = len(items)
        items.sort(key=lambda t: (t.queue_priority, t.created_at))
        return items[offset : offset + limit], total_count

    async def claim_next(self, moderator_id: UUID) -> TicketReadSchema | None:
        """Имитируем SELECT FOR UPDATE SKIP LOCKED LIMIT 1.

        Берём первый PENDING-тикет по (queue_priority ASC, created_at ASC), переводим
        в IN_REVIEW + claimed_by + claimed_at. В тесте этого достаточно — реальный
        SQL покрывается в M3/integration-тестах.
        """
        self.claim_next_calls.append(moderator_id)
        pending = [t for t in self.by_id.values() if t.status == TicketStatus.PENDING]
        if not pending:
            return None
        pending.sort(key=lambda t: (t.queue_priority, t.created_at))
        ticket = pending[0]
        ticket.status = TicketStatus.IN_REVIEW
        ticket.claimed_by = moderator_id
        ticket.claimed_at = datetime.now(UTC)
        self.by_id[ticket.id] = ticket
        return ticket

    async def update_in_session(self, session: Any, data: TicketUpdateSchema) -> TicketReadSchema | None:
        """In-transaction update — для use-cases, enqueue'ящих outbox в той же tx.

        Fake реализация делегирует к обычному update(), session игнорируем.
        """
        _ = session
        return await self.update(data)

    async def get_active_for_product(self, product_id: UUID) -> TicketReadSchema | None:
        """Активный (не ARCHIVED) тикет для товара. product_id уникален → не больше одного."""
        active = [t for t in self.by_id.values() if t.product_id == product_id and t.status != TicketStatus.ARCHIVED]
        if not active:
            return None
        active.sort(key=lambda t: t.created_at, reverse=True)
        return active[0]

    async def archive_for_product(self, product_id: UUID) -> int:
        """ARCHIVE все не-ARCHIVED тикеты товара (включая HARD_BLOCKED). Идемпотентно."""
        affected = 0
        for ticket in self.by_id.values():
            if ticket.product_id == product_id and ticket.status != TicketStatus.ARCHIVED:
                ticket.status = TicketStatus.ARCHIVED
                self.updated.append(TicketUpdateSchema(id=ticket.id, status=TicketStatus.ARCHIVED))
                affected += 1
        return affected


class FakeSessionManager:
    """Минимальный stub: async-CM возвращает себя; реальный коммит здесь не нужен,
    use-case под капотом просто использует `session` как маркер для outbox.enqueue().
    """

    class _Session:
        async def execute(self, _stmt: Any) -> Any:
            raise RuntimeError('FakeSessionManager: use-case должен ходить через repo, не SQL')

        async def flush(self) -> None:
            pass

    class _Context:
        async def __aenter__(self):
            return FakeSessionManager._Session()

        async def __aexit__(self, *args):
            return False

    def get_session(self):
        return FakeSessionManager._Context()


class FakeOutboxRepository:
    """Фиксирует enqueue-вызовы. В продакшне делает INSERT в outbox в той же транзакции."""

    def __init__(self):
        self.enqueued: list[OutboxEnqueueSchema] = []

    async def enqueue(self, session: Any, data: OutboxEnqueueSchema):
        self.enqueued.append(data)
        return data


class FakeModerationB2BClient:
    """Фейк B2B-клиента — мокаем ТОЛЬКО HTTP-границу к B2B.

    `get_product` отдаёт сконфигурированный товар (по умолчанию — с одним SKU).
    Тесты подменяют `product` на None / товар без skus, чтобы прогнать прекондишн.
    Фиксирует вызовы в `calls`, чтобы проверять, что B2B НЕ дёргается до того,
    как пройдут проверки статуса/владельца.
    """

    def __init__(self, product: dict[str, Any] | None = ...):  # type: ignore[assignment]
        # По умолчанию — валидный товар с одним SKU (happy path).
        self.product: dict[str, Any] | None = {'skus': [{'id': str(uuid4())}]} if product is ... else product
        self.calls: list[UUID] = []

    async def get_product(self, product_id: UUID) -> dict[str, Any] | None:
        self.calls.append(product_id)
        return self.product
