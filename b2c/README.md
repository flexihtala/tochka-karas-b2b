# b2c/ — витрина покупателя

Bootstrap + auth + buyers/me + addresses + payment-methods — PR `forge/karas/b2c-bootstrap` (Phase 4).

Затем 15 квестов:

- US-CAT-01..05 (каталог)
- US-CART-01..05 (корзина + главная)
- US-ORD-01..05 (заказы)

## Запуск

```bash
cd b2c
uv sync --all-packages --all-extras
uv run alembic upgrade head
uv run uvicorn cmd.rest:app --reload --port 8003
```

## Тесты

```bash
cd b2c
uv run pytest -v
```

## ADR — Идентификация пользователя в `/favorites` (US-CART-01)

Источник `user_id` для всех `/favorites` эндпоинтов (POST, DELETE, GET) — **только JWT
claim `sub`**. Альтернативы — query-параметр `?user_id=...` (как в исходном OpenAPI)
и заголовок `X-User-Id` — отклонены: оба позволяют клиенту подделать идентификатор
владельца и совершить IDOR (добавить/удалить избранное чужому пользователю). При
выборе JWT любая попытка передать `user_id` в теле/query/заголовках просто
игнорируется (схема запроса использует `extra='ignore'`), а DELETE физически
ограничен `WHERE user_id = current_user.id`. Критерий: предотвращение IDOR
(см. `neomarket-canon/security-guidelines.md`).

## ADR — Хранение иерархии категорий (US-CAT-05)

Рассмотрены три варианта: PostgreSQL `ltree`, adjacency-list (`parent_id`),
materialized path. `ltree` даёт O(1) на breadcrumbs и поддеревьях, но требует
расширения и переписывает SQL-доступ; materialized path даёт быстрый префиксный
поиск, но делает обнаружение orphan-нод нетривиальным (рассинхрон `path` и
`parent_id`). **На MVP выбран adjacency-list**: дерево категорий маленькое и
читается одним запросом, breadcrumbs строятся в памяти за O(depth), orphan-нода
ловится явной проверкой `parent_id NOT IN (id)`. Если каталог разрастётся
(>10k категорий или глубже 6 уровней), мигрируем на `ltree` отдельным шагом.

## ADR — Идентификация гостевой корзины: X-Session-Id

Для гостевых корзин выбран заголовок `X-Session-Id` (opaque UUID, генерируемый
фронтом). Альтернативы — HTTP-cookie (требует same-origin или CORS-credentials —
плохо для мобильных приложений) и temp-JWT (привязка серверного состояния
выпуска токенов к анонимам — оверхед, ещё и подделать подпись нельзя, но
ротировать тоже нельзя без логина). Заголовок `X-Session-Id` одинаково удобен
для web и нативных клиентов, не требует CORS-credentials, и риск подделки
ограничен enumeration UUID v4 (~2^122 пространство). Чтобы избежать кросс-IDOR,
при наличии валидного JWT заголовок ИГНОРИРУЕТСЯ (исключение — `/cart/merge`).

## ADR — Buyers как отдельная таблица

Решено вести **отдельную таблицу `users`** внутри сервиса b2c (а не один общий
"людской" каталог между сервисами). Аргументы:

- B2B уже имеет свою таблицу `users` (продавцы), Moderation — свою (модераторы).
  Логично, что b2c тоже владеет своими покупателями.
- Чистая граница владения: bcrypt/jwt-секреты, `password_changed_at`, `is_active`
  — это локальные состояния b2c, без зависимостей от других сервисов.
- Service-to-service общение идёт через JWT (`shared.auth_lib`), а UUID юзеров
  глобально уникальны, так что нет коллизий при ссылках из заказов/корзин.
- Меньше связности между сервисами на уровне БД — каждый сервис свободен в
  эволюции схемы (добавить `date_of_birth`, `loyalty_tier` и т.д.).

## ADR — Idempotency для B2B-events (US-ORD-04)

POST `/api/v1/events/product` идемпотентен по `(sender_service, idempotency_key)`.
Хранилище — **таблица `processed_events`** (через `shared.inbox.IdempotentHandler`),
а не Redis+TTL и не отдельная колонка на доменной таблице. Аргументы:

- Транзакционно: запись в processed_events и доменные побочные эффекты
  (`sku_unavailability`) живут в одной DB-транзакции, без распределённого
  two-phase commit с внешним TTL-хранилищем.
- Универсально: shared.inbox используется всеми сервисами, не вводим
  per-domain idempotency-колонки на каждой таблице.
- Достаточно для требований SLA на дедупликацию (24h TTL по канону достигается
  scheduled job-ом по `created_at`; здесь не реализуется, но архитектурно нет
  препятствий — это всего лишь DELETE WHERE created_at < now() - 24h).

Cart-items НЕ модифицируются при событии: `cart_item.unavailable_reason`
вычисляется на лету при `GET /cart` enrichment'е из B2B (см. US-CART-03).
Локально пишем sku в `sku_unavailability` — это кэш для аналитики/инвалидации,
не источник истины. Orders не затрагиваются: цены зафиксированы при checkout
(canon Flow B2C-12).

## ADR — `notify_on` хранится как `ARRAY[str]` (PG)

Для `product_subscriptions.notify_on` рассмотрели три варианта: `ARRAY[str]` (PG),
отдельную таблицу `subscription_events` (1:N) и `JSONB`. Выбран `ARRAY(String(32))`:
доменное множество событий маленькое и стабильное (`PRICE_DROP`, `BACK_IN_STOCK`),
филтруемость через GIN/`ANY()` на массивах в PG достаточна для будущих запросов
типа "у кого подписка на PRICE_DROP" без join-ов. Отдельная таблица даёт более
строгую целостность и индексы, но даёт 1:N-сложность миграций и join при чтении —
оверкилл для двух значений в MVP. JSONB слишком слабо типизирован для столь
ограниченного словаря. Если множество событий вырастет или появятся per-event
атрибуты (пороги цены и т.п.) — мигрируем в отдельную таблицу разовой миграцией.
