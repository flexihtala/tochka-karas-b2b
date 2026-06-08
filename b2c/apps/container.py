from contextlib import asynccontextmanager
from typing import ClassVar, AsyncIterator

from dishka import AsyncContainer, make_async_container, Provider
from dishka.integrations.fastapi import FastapiProvider


class ContainerManager:
    container: ClassVar[AsyncContainer | None] = None

    @classmethod
    def create(cls, application_providers: list[Provider]) -> AsyncContainer:
        if cls.container is None:
            cls.container = make_async_container(*application_providers)
        return cls.container


@asynccontextmanager
async def get_container(
    application_providers: list[Provider] | None = None,
) -> AsyncIterator[AsyncContainer]:
    container = ContainerManager.container
    if container is None:
        if application_providers is None:
            application_providers = [FastapiProvider()]
        container = ContainerManager.create(application_providers=application_providers)
    async with container() as nested_container:
        yield nested_container
