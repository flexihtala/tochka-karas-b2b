from apps.outbox.models import ModerationOutboxEvent
from shared.outbox import OutboxRepository


class ModerationOutboxRepository(OutboxRepository[ModerationOutboxEvent]):
    """Конкретизация generic OutboxRepository под модель Moderation.

    Use-cases вызывают `enqueue(session, data)` в той же транзакции, что и
    UPDATE по тикету. Воркер (M3) — `claim_batch()` + `mark_sent()` / `mark_retry()`.
    """

    model_type = ModerationOutboxEvent
