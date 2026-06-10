from apps.home.models import BannerClick
from apps.home.schemas.db import (
    BannerClickCreateSchema,
    BannerClickReadSchema,
    BannerClickUpdateSchema,
)
from shared.db import DBCrudRepository


class BannerClickRepository(
    DBCrudRepository[
        BannerClick,
        BannerClickCreateSchema,
        BannerClickReadSchema,
        BannerClickUpdateSchema,
    ]
):
    """Запись кликов по баннеру.

    Хранилище для CTR/аналитики. См. ADR в PR (relational table выбран как MVP-вариант).
    """
