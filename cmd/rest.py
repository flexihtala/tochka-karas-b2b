from fastapi import FastAPI
from dishka.integrations.fastapi import setup_dishka as fastapi_setup_dishka
from dishka.integrations.fastapi import FastapiProvider
from apps.auth.middleware import AuthMiddleware
from apps.auth.services.jwt_service import JwtService
from apps.errors import setup_error_handlers
from apps.router import router
from apps.depends import providers
from apps.container import ContainerManager
from settings import settings


def create_app() -> FastAPI:
    app = FastAPI(title='tochka-karas-b2b', docs_url='/docs', openapi_url='/docs.json')
    app.add_middleware(AuthMiddleware, jwt_service=JwtService(settings))
    app.include_router(router)
    setup_error_handlers(app)
    application_providers = [FastapiProvider(), *providers]
    container = ContainerManager.create(application_providers)
    fastapi_setup_dishka(container, app)
    return app


app = create_app()
