"""FastAPI application factory for HomeMind AI."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from homemind import __version__
from homemind.api import (
    routes_conversations,
    routes_knowledge,
    routes_memories,
    routes_system,
    routes_tools,
)
from homemind.api.deps import attach_state, build_state
from homemind.config.settings import Settings, get_settings
from homemind.models.schemas import ErrorDetail, ErrorResponse

log = logging.getLogger("homemind.api")


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=ErrorDetail(code=code, message=message)
        ).model_dump(),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    app = FastAPI(
        title="HomeMind AI",
        description="Local-first private personal AI assistant.",
        version=__version__,
    )
    attach_state(app, build_state(settings))

    # -- error handlers (consistent schema, no sensitive data) -------------- #
    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(422, "validation_error", "Invalid request data.")

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return _error_response(500, "internal_error", "An unexpected error occurred.")

    # -- routes -------------------------------------------------------------- #
    app.include_router(routes_system.router)
    app.include_router(routes_conversations.router)
    app.include_router(routes_knowledge.router)
    app.include_router(routes_memories.router)
    app.include_router(routes_tools.router)
    return app


def main() -> None:
    """Entry point: ``homemind-api``. Binds to loopback only by default."""
    import uvicorn

    settings = get_settings()
    log.info(
        "Starting HomeMind AI API on %s:%s (provider=%s, model=%s)",
        settings.host,
        settings.port,
        settings.provider,
        settings.model,
    )
    uvicorn.run(
        "homemind.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
