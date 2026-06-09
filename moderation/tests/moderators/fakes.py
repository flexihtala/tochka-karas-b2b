# Реэкспорт fakes из auth/, чтобы тесты moderators могли использовать те же стабы Moderator-репо/хешера.
from tests.auth.fakes import (
    FakeModeratorRepository as FakeModeratorRepository,
)
from tests.auth.fakes import (
    FakePasswordHasher as FakePasswordHasher,
)
from tests.auth.fakes import (
    make_moderator_read_schema as make_moderator_read_schema,
)
