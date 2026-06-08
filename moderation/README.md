# moderation/ — сервис модерации товаров

Bootstrap по спеке `moderation/neomarket-moderation.yaml` (23 op) +
канон `flows/moderation-flows.md`.

Заполняется в PR `forge/karas/moderation-m1-bootstrap` (Phase 3, агент G).

## ADR-M3: место бизнес-логики тикетов

В M3 use-case `HandleB2BEventUseCase` дергает `TicketRepository` напрямую,
без промежуточного `TicketService`. На текущем этапе поведение тривиально
(CREATED → INSERT PENDING; EDITED → UPDATE → PENDING; DELETED → bulk
UPDATE → ARCHIVED) и единственный потребитель — входящий B2B-канал.
Когда в M4/M5 появятся claim/release/decision с FSM-переходами по статусу,
история и outbox-событиями MODERATED/BLOCKED → B2B, тогда оправдано
вынести логику в отдельный `TicketService` поверх репозитория. Сейчас
такой слой был бы пустой обёрткой и противоречил бы остальному стилю
сервиса (use-cases в `auth`/`moderators` тоже работают с репо напрямую).
