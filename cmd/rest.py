from fastapi import FastAPI
from dishka.integrations.fastapi import setup_dishka as fastapi_setup_dishka
from dishka.integrations.fastapi import FastapiProvider
from ..apps.router import router
from ..apps.depends import providers
from ..apps.container import ContainerManager


def create_app() -> FastAPI:
    app = FastAPI(title='json-storage', docs_url='/docs', openapi_url='/docs.json')
    app.include_router(router)
    application_providers = [FastapiProvider(), *providers]
    container = ContainerManager.create(application_providers)
    fastapi_setup_dishka(container, app)
    return app


app = create_app()
