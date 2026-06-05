"""InventoryRepository — мутации количества SKU под блокировкой строк.

Ключевая операция — резерв/анрезерв всего пакета SKU под `SELECT ... FOR UPDATE`
в одной транзакции. Это даёт all-or-nothing семантику: либо все SKU доступны
и обновляются атомарно, либо весь reserve откатывается (см. ADR).

Use-case передаёт сессию `AsyncSession` явно, чтобы:
  1. SKU UPDATE и INSERT processed_events были в одной транзакции
     (атомарная idempotency).
  2. По выходу с InventoryConflictError транзакция откатилась
     контекст-менеджером session_manager.

См. neomarket-canon/flows/b2b-flows.md#reserve-sku.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.inventory.enums import ReserveFailureReason
from apps.inventory.errors import InventoryConflictError
from apps.skus.models import SKU


@dataclass(frozen=True)
class ReserveItemResult:
    sku_id: UUID
    reserved_quantity: int  # сколько только что зарезервировали
    remaining_stock: int  # active_quantity после операции
    reached_zero: bool  # active_quantity стал 0 → нужно отправить SKU_OUT_OF_STOCK


@dataclass(frozen=True)
class UnreserveItemResult:
    sku_id: UUID


class InventoryRepository:
    """Узкий репозиторий: операции reserve/unreserve по списку (sku_id, qty).

    Принимает `session: AsyncSession` извне. Use-case управляет границей
    транзакции.
    """

    async def reserve(
        self,
        session: AsyncSession,
        items: list[tuple[UUID, int]],
    ) -> list[ReserveItemResult]:
        """All-or-nothing резервирование внутри переданной транзакции.

        Поведение:
          1. `SELECT ... WHERE id IN (...) FOR UPDATE` (в детерминированном
             порядке sku_id — снижает риск deadlock'ов при пересекающихся
             параллельных reserve'ах).
          2. Для каждого item: проверяет, что SKU существует и
             `active_quantity >= quantity`. Если хотя бы один не проходит —
             поднимает `InventoryConflictError`. Вызывающий код выходит из
             session-контекста с исключением → SQLAlchemy откатывает
             транзакцию автоматически.
          3. Иначе: `active_quantity -= quantity`,
             `reserved_quantity += quantity`. flush.
          4. Возвращает список `ReserveItemResult` с новым remaining_stock
             и флагом `reached_zero` (для последующего outbox SKU_OUT_OF_STOCK).
        """
        sorted_ids = sorted({sku_id for sku_id, _ in items})
        if not sorted_ids:
            return []
        requested_by_id: dict[UUID, int] = {sku_id: qty for sku_id, qty in items}

        stmt = select(SKU).where(SKU.id.in_(sorted_ids)).order_by(SKU.id).with_for_update()
        result = await session.execute(stmt)
        skus: list[SKU] = list(result.scalars().all())
        skus_by_id: dict[UUID, SKU] = {sku.id: sku for sku in skus}

        # Валидация (all-or-nothing)
        failed_items: list[dict] = []
        for sku_id in sorted_ids:
            requested = requested_by_id[sku_id]
            sku = skus_by_id.get(sku_id)
            if sku is None:
                failed_items.append(
                    {
                        'sku_id': str(sku_id),
                        'requested': requested,
                        'available': 0,
                        'reason': ReserveFailureReason.NOT_FOUND.value,
                    }
                )
                continue
            if sku.active_quantity < requested:
                reason = (
                    ReserveFailureReason.OUT_OF_STOCK
                    if sku.active_quantity == 0
                    else ReserveFailureReason.INSUFFICIENT_STOCK
                )
                failed_items.append(
                    {
                        'sku_id': str(sku_id),
                        'requested': requested,
                        'available': sku.active_quantity,
                        'reason': reason.value,
                    }
                )
        if failed_items:
            raise InventoryConflictError(failed_items=failed_items)

        # Применение
        results: list[ReserveItemResult] = []
        for sku_id in sorted_ids:
            requested = requested_by_id[sku_id]
            sku = skus_by_id[sku_id]
            sku.active_quantity = sku.active_quantity - requested
            sku.reserved_quantity = sku.reserved_quantity + requested
            results.append(
                ReserveItemResult(
                    sku_id=sku_id,
                    reserved_quantity=requested,
                    remaining_stock=sku.active_quantity,
                    reached_zero=sku.active_quantity == 0,
                )
            )

        await session.flush()
        return results

    async def unreserve(
        self,
        session: AsyncSession,
        items: list[tuple[UUID, int]],
    ) -> list[UnreserveItemResult]:
        """Компенсирующая операция: для каждого SKU
        `reserved_quantity -= quantity`, `active_quantity += quantity`.

        Идемпотентность гарантируется на уровне use-case через processed_events.
        Отсутствующий SKU игнорируется (best-effort компенсация — канон не
        требует ошибку для этого случая).
        """
        sorted_ids = sorted({sku_id for sku_id, _ in items})
        if not sorted_ids:
            return []
        requested_by_id: dict[UUID, int] = {sku_id: qty for sku_id, qty in items}

        stmt = select(SKU).where(SKU.id.in_(sorted_ids)).order_by(SKU.id).with_for_update()
        result = await session.execute(stmt)
        skus: list[SKU] = list(result.scalars().all())
        skus_by_id: dict[UUID, SKU] = {sku.id: sku for sku in skus}

        results: list[UnreserveItemResult] = []
        for sku_id in sorted_ids:
            sku = skus_by_id.get(sku_id)
            if sku is None:
                continue
            qty = requested_by_id[sku_id]
            sku.reserved_quantity = sku.reserved_quantity - qty
            sku.active_quantity = sku.active_quantity + qty
            results.append(UnreserveItemResult(sku_id=sku_id))

        await session.flush()
        return results
