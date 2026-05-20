from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from settings import Settings


class SessionManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker[AsyncSession] | None = None

    def get_engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(self.settings.database_url, pool_pre_ping=True)
        return self._engine

    def create_session_maker(self) -> async_sessionmaker[AsyncSession]:
        if self._session_maker is None:
            self._session_maker = async_sessionmaker(
                self.get_engine(),
                expire_on_commit=False,
                autoflush=False,
            )
        return self._session_maker

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        session_maker = self.create_session_maker()
        async with session_maker() as session:
            async with session.begin():
                yield session
