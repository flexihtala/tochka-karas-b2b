from datetime import UTC, datetime
from uuid import UUID, uuid4

from apps.tickets.enums import TicketStatus
from apps.tickets.schemas.db import TicketCreateSchema, TicketReadSchema, TicketUpdateSchema


def make_ticket_read_schema(
    *,
    id: UUID | None = None,
    product_id: UUID | None = None,
    seller_id: UUID | None = None,
    status: str = TicketStatus.PENDING.value,
    claimed_by: UUID | None = None,
    claimed_at: datetime | None = None,
    blocking_reason_id: UUID | None = None,
    moderator_comment: str | None = None,
) -> TicketReadSchema:
    now = datetime.now(UTC)
    return TicketReadSchema(
        id=id or uuid4(),
        product_id=product_id or uuid4(),
        seller_id=seller_id or uuid4(),
        status=status,
        claimed_by=claimed_by,
        claimed_at=claimed_at,
        blocking_reason_id=blocking_reason_id,
        moderator_comment=moderator_comment,
        created_at=now,
        updated_at=now,
    )


class FakeTicketRepository:
    """In-memory подмена TicketRepository для use-case-тестов.

    Хранит тикеты в by_id, дополнительно отслеживает created/updated/archived вызовы
    для assert-ов.
    """

    def __init__(self):
        self.by_id: dict[UUID, TicketReadSchema] = {}
        self.created: list[TicketCreateSchema] = []
        self.updated: list[TicketUpdateSchema] = []
        self.archived_product_ids: list[UUID] = []

    async def create(self, data: TicketCreateSchema) -> TicketReadSchema:
        self.created.append(data)
        ticket = make_ticket_read_schema(
            id=data.id or uuid4(),
            product_id=data.product_id,
            seller_id=data.seller_id,
            status=data.status,
            claimed_by=data.claimed_by,
            claimed_at=data.claimed_at,
            blocking_reason_id=data.blocking_reason_id,
            moderator_comment=data.moderator_comment,
        )
        self.by_id[ticket.id] = ticket
        return ticket

    async def update(self, data: TicketUpdateSchema) -> TicketReadSchema | None:
        existing = self.by_id.get(data.id)
        if existing is None:
            return None
        self.updated.append(data)
        update_payload = data.model_dump(exclude_unset=True, exclude={'id'})
        for key, value in update_payload.items():
            setattr(existing, key, value)
        return existing

    async def get_active_for_product(self, product_id: UUID) -> TicketReadSchema | None:
        active_statuses = {TicketStatus.PENDING.value, TicketStatus.IN_REVIEW.value}
        for ticket in self.by_id.values():
            if ticket.product_id == product_id and ticket.status in active_statuses:
                return ticket
        return None

    async def archive_for_product(self, product_id: UUID) -> int:
        self.archived_product_ids.append(product_id)
        count = 0
        for ticket in self.by_id.values():
            if ticket.product_id == product_id and ticket.status != TicketStatus.ARCHIVED.value:
                ticket.status = TicketStatus.ARCHIVED.value
                count += 1
        return count

    async def count_by_status(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for ticket in self.by_id.values():
            result[ticket.status] = result.get(ticket.status, 0) + 1
        return result

    async def count_by_moderator(self) -> list[tuple[UUID, dict[str, int]]]:
        per_mod: dict[UUID, dict[str, int]] = {}
        for ticket in self.by_id.values():
            if ticket.claimed_by is None:
                continue
            per_mod.setdefault(ticket.claimed_by, {})
            per_mod[ticket.claimed_by][ticket.status] = per_mod[ticket.claimed_by].get(ticket.status, 0) + 1
        return list(per_mod.items())

    async def total_count(self) -> int:
        return len(self.by_id)

    def add(self, ticket: TicketReadSchema) -> None:
        self.by_id[ticket.id] = ticket
