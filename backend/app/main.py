"""Application factory. `uvicorn app.main:app` serves the module-level `app`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import router as api_v1_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.db.session import dispose_engine

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log.info("startup", env=settings.app_env, version=__version__)
    yield
    await dispose_engine()
    log.info("shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title="JD x Resume Scorer API",
        version=__version__,
        lifespan=lifespan,
        # Hide interactive docs in prod; the OpenAPI schema is still exported for the frontend.
        docs_url=None if settings.is_prod else "/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    # Added last = outermost, so every response (incl. CORS/errors) gets a request id.
    app.add_middleware(RequestContextMiddleware)

    register_error_handlers(app)
    app.include_router(api_v1_router)
    return app


app = create_app()
