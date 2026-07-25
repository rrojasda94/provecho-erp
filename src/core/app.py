from fastapi import FastAPI

from src.config.settings import settings
from src.modules.inventory.api.routers import router as inventory_router
from src.modules.inventory.application import listeners as inventory_listeners
from src.modules.sales.api.kds_routers import router as kds_router
from src.modules.sales.api.routers import router as sales_router
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
    app.include_router(inventory_router, prefix="/api/v1")
    app.include_router(sales_router, prefix="/api/v1")
    app.include_router(kds_router, prefix="/api/v1")
    inventory_listeners.register()
    return app
