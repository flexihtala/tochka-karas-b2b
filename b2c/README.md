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
