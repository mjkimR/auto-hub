import os
from contextlib import asynccontextmanager
from pathlib import Path

from app.features import tasks
from app.features.project_management.projects.services import ProjectError
from app.router import router
from app_layer_base.base.exceptions.handler import set_exception_handler
from app_layer_base.core import middlewares
from app_layer_base.core.log import logger
from fastapi import FastAPI
from starlette.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles


def _resolve_ui_dist() -> Path | None:
    custom_path = os.getenv("UI_DIST_PATH")
    if custom_path:
        p = Path(custom_path)
        if p.is_dir() and (p / "index.html").is_file():
            return p
    container_path = Path(__file__).resolve().parent.parent / "ui_dist"
    if container_path.is_dir() and (container_path / "index.html").is_file():
        return container_path
    return None


def get_lifespan():
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting app lifespan")
        tasks.autodiscover()
        yield
        logger.info("End of app lifespan")

    return lifespan


def create_app():
    """Create the FastAPI app and include the router."""
    lifespan = get_lifespan()
    app = FastAPI(
        title="ExampleApp",
        version="0.0.1",
        lifespan=lifespan,
        swagger_ui_parameters={
            "persistAuthorization": True,
            "docExpansion": "none",
            "filter": True,
        },
    )

    # Others
    middlewares.timeout_middleware.add_middleware(app)
    middlewares.query_counter.add_middleware(app)

    # Security middleware
    middlewares.security_header.add_middleware(app)
    middlewares.cors_middleware.add_middleware(app)

    # Request ID middleware (Last one to ensure all logs have request ID)
    middlewares.request_id_middleware.add_middleware(app)

    app.include_router(router)

    set_exception_handler(app)

    @app.exception_handler(ProjectError)
    async def project_error_handler(request, exc: ProjectError):
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

    ui_dist = _resolve_ui_dist()
    if ui_dist is not None:
        app_dir = ui_dist / "_app"
        if app_dir.is_dir():
            app.mount("/_app", StaticFiles(directory=str(app_dir)), name="spa_app")

        @app.get("/")
        async def root_spa():
            return FileResponse(ui_dist / "index.html")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            target = (ui_dist / full_path).resolve()
            if full_path and target.is_relative_to(ui_dist.resolve()) and target.is_file():
                return FileResponse(target)
            return FileResponse(ui_dist / "index.html")
    else:

        @app.get("/")
        async def root_docs():
            return RedirectResponse(url="/docs")

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="localhost", port=8389)
