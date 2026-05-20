"""OutboxWorker — asyncio task, периодически отправляет PENDING-события из outbox.

Запускается в FastAPI lifespan:

    @asynccontextmanager
    async def lifespan(app):
        worker = OutboxWorker(session_manager, repository, dispatch_fn, poll_interval=2.0)
        task = asyncio.create_task(worker.run())
        yield
        worker.stop()
        await task
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from shared.db.session_manager import SessionManager
from shared.outbox.fields import OutboxFieldsMixin
from shared.outbox.repository import OutboxRepository

logger = logging.getLogger(__name__)

# Backoff: 30, 60, 120, 240, 480, 960, ...  (max 10 попыток → FAILED)
DEFAULT_BACKOFF_SECONDS = [30, 60, 120, 240, 480, 960, 1920, 3840, 7680, 15360]
MAX_RETRIES = 10


DispatchFn = Callable[[OutboxFieldsMixin], Awaitable[None]]
"""Корутина, которая отправляет одно событие по HTTP. Должна бросать исключение
при сбое (любая HTTP 5xx, timeout, etc.) — worker запланирует retry."""


class OutboxWorker:
    def __init__(
        self,
        session_manager: SessionManager,
        repository: OutboxRepository,  # type: ignore[type-arg]
        dispatch: DispatchFn,
        poll_interval: float = 2.0,
        batch_size: int = 10,
    ):
        self.session_manager = session_manager
        self.repository = repository
        self.dispatch = dispatch
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self._stopping = asyncio.Event()

    def stop(self) -> None:
        self._stopping.set()

    async def run(self) -> None:
        logger.info('OutboxWorker started')
        while not self._stopping.is_set():
            try:
                processed = await self._tick()
            except Exception as exc:  # noqa: BLE001 — worker должен переживать любые ошибки
                logger.exception('OutboxWorker tick failed: %s', exc)
                processed = 0
            if processed == 0:
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self.poll_interval)
                except asyncio.TimeoutError:
                    pass
        logger.info('OutboxWorker stopped')

    async def _tick(self) -> int:
        async with self.session_manager.get_session() as session:
            events = await self.repository.claim_batch(session, batch_size=self.batch_size)
            if not events:
                return 0
            for event in events:
                try:
                    await self.dispatch(event)
                    await self.repository.mark_sent(session, event.id)  # type: ignore[attr-defined]
                except Exception as exc:  # noqa: BLE001
                    retry_count = event.retry_count or 0  # type: ignore[attr-defined]
                    if retry_count + 1 >= MAX_RETRIES:
                        await self.repository.mark_failed(session, event.id, str(exc))  # type: ignore[attr-defined]
                        logger.error('OutboxEvent %s exhausted retries, marked FAILED', event.id)  # type: ignore[attr-defined]
                    else:
                        delay = DEFAULT_BACKOFF_SECONDS[min(retry_count, len(DEFAULT_BACKOFF_SECONDS) - 1)]
                        next_retry = datetime.now(UTC) + timedelta(seconds=delay)
                        await self.repository.mark_retry(session, event.id, next_retry, str(exc))  # type: ignore[attr-defined]
                        logger.warning(
                            'OutboxEvent %s retry %d scheduled at %s: %s',
                            event.id,  # type: ignore[attr-defined]
                            retry_count + 1,
                            next_retry.isoformat(),
                            exc,
                        )
        return len(events)
