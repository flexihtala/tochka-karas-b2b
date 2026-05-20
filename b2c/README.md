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

## ADR — Хранение иерархии категорий (US-CAT-05)

Рассмотрены три варианта: PostgreSQL `ltree`, adjacency-list (`parent_id`),
materialized path. `ltree` даёт O(1) на breadcrumbs и поддеревьях, но требует
расширения и переписывает SQL-доступ; materialized path даёт быстрый префиксный
поиск, но делает обнаружение orphan-нод нетривиальным (рассинхрон `path` и
`parent_id`). **На MVP выбран adjacency-list**: дерево категорий маленькое и
читается одним запросом, breadcrumbs строятся в памяти за O(depth), orphan-нода
ловится явной проверкой `parent_id NOT IN (id)`. Если каталог разрастётся
(>10k категорий или глубже 6 уровней), мигрируем на `ltree` отдельным шагом.

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
