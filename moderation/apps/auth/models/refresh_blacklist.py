import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class RefreshBlacklist(Base):
    __tablename__ = 'refresh_blacklist'

    jti: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @property
    def id(self) -> uuid.UUID:
        return self.jti
