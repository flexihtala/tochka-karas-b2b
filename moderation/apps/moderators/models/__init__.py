# Модели Moderator живут в apps/auth/models/moderator.py (используется в JWT-флоу).
# Тут переэкспортируем для удобства и для alembic autogenerate (env.py подхватит обе папки).
from apps.auth.models import Moderator as Moderator
