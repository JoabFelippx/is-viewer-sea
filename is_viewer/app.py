"""Monta a aplicação e controla a vida útil das conexões com o broker."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .cameras import CameraService
from .config import Settings
from .messaging.hub import FrameHub
from .messaging.rpc import RpcClient
from .web.camera_api import router as camera_router
from .web.pages import WEB_DIRECTORY
from .web.routes import router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        rpc = RpcClient(settings.broker_uri)
        try:
            hub = FrameHub(settings.broker_uri)
            try:
                app.state.hub = hub
                app.state.cameras = CameraService(rpc)
                hub.start()
                yield
            finally:
                hub.stop()
        finally:
            rpc.close()

    app = FastAPI(title="IS viewer", lifespan=lifespan)
    app.state.settings = settings
    # Os arquivos estáticos devem ser encontrados antes das rotas genéricas.
    app.mount("/static", StaticFiles(directory=WEB_DIRECTORY / "static"), name="static")
    app.include_router(camera_router)
    app.include_router(router)
    return app


app = create_app()
