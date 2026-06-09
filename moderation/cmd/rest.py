from dishka.integrations.fastapi import FastapiProvider
from dishka.integrations.fastapi import setup_dishka as fastapi_setup_dishka
from fastapi import FastAPI

from apps.container import ContainerManager
from apps.depends import providers
from apps.errors import setup_error_handlers
from apps.router import router
from settings import settings
from shared.auth_lib import AuthMiddleware, JwtService


def create_app() -> FastAPI:
    app = FastAPI(title='neomarket-moderation', docs_url='/docs', openapi_url='/docs.json')
    app.add_middleware(AuthMiddleware, jwt_service=JwtService(settings))
    app.include_router(router)
    setup_error_handlers(app)
    application_providers = [FastapiProvider(), *providers]
    container = ContainerManager.create(application_providers)
    fastapi_setup_dishka(container, app)
    return app


app = create_app()
