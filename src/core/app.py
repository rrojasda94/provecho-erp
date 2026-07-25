from fastapi import FastAPI

from src.config.settings import settings
from src.modules.users.api.routers import router as users_router


def create_app() -> FastAPI:
    """Crea la aplicación y registra los routers de cada módulo activo."""
    app = FastAPI(
        title="Provecho ERP",
        version="0.1.0",
        description="ERP modular para grupo de restaurantes multi-marca.",
    )

    @app.get("/health", tags=["core"])
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name, "environment": settings.environment}

    app.include_router(users_router, prefix="/api/v1")
    return app
