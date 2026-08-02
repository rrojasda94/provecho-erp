import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.config.settings import settings
from src.core import error_handlers
from src.core.dashboard_router import router as dashboard_router
from src.core.health_router import router as health_router
from src.core.logging_config import configurar_logging, request_id_var
from src.core.sentry import iniciar_sentry
from src.core.sync.api.routers import router as sync_router
from src.core.tenant import FueraDeAlcance
from src.modules.accounting.api.routers import router as accounting_router
from src.modules.accounting.application import listeners as accounting_listeners
from src.modules.inventory.api.routers import router as inventory_router
from src.modules.inventory.application import listeners as inventory_listeners
from src.modules.marketing.api.routers import router as marketing_router
from src.modules.marketing.application import listeners as marketing_listeners
from src.modules.production.api.routers import router as production_router
from src.modules.purchases.api.routers import router as purchases_router
from src.modules.rrhh.api.routers import router as rrhh_router
from src.modules.sales.api.kds_routers import router as kds_router
from src.modules.sales.api.routers import router as sales_router
from src.modules.users.api import error_handlers as users_error_handlers
from src.modules.users.api.routers import router as users_router

log = logging.getLogger("provecho.app")

# Ruido: el chequeo de salud lo golpea el monitor cada pocos segundos.
RUTAS_SIN_LOG = frozenset({"/health"})

# Descripción de cada tag en /docs y en el contrato OpenAPI exportado
# (`src/core/openapi_export.py`). Sin esto FastAPI agrupa por nombre pero
# sin explicar qué es cada grupo — un cliente externo generando SDK a
# partir del JSON no tiene más contexto que el nombre.
TAGS_METADATA = [
    {
        "name": "core",
        "description": "Salud del proceso (liveness/readiness) y estado de sync del hub. Sin auth.",
    },
    {
        "name": "auth",
        "description": "Login por PIN, refresh rotativo, logout. Sin JWT previo.",
    },
    {"name": "users", "description": "Perfil del usuario autenticado (`/users/me`)."},
    {
        "name": "personas",
        "description": "Party model transversal: base de trabajador/cliente/usuario natural.",
    },
    {
        "name": "users-admin",
        "description": "CRUD de usuarios, roles, permisos y asignaciones (`users.gestionar`).",
    },
    {
        "name": "gerencia",
        "description": "Matriz de aprobaciones por empresa, en vez de umbrales fijos por módulo.",
    },
    {
        "name": "sales",
        "description": "Ventas y PDV: venta, cobro, catálogo comercial, comprobante electrónico.",
    },
    {
        "name": "kds",
        "description": "Pantallas de cocina: avance de pedido, comanda, despacho.",
    },
    {
        "name": "inventory",
        "description": "Catálogo de artículos, stock por almacén, movimientos y ajustes.",
    },
    {"name": "purchases", "description": "Proveedores y ciclo de orden de compra."},
    {
        "name": "production",
        "description": "Órdenes de producción (fabricación) y costeo.",
    },
    {
        "name": "accounting",
        "description": "Libro contable, pago a proveedor (tesorería).",
    },
    {
        "name": "rrhh",
        "description": "Ciclo laboral: contrato, nómina, disciplina, permisos, asistencia.",
    },
    {
        "name": "marketing",
        "description": (
            "Campañas, calendario de contenido, leads con atribución a la venta "
            "y encuesta de satisfacción."
        ),
    },
    {
        "name": "dashboard",
        "description": "Agregado gerencial de solo lectura: ventas del día, stock crítico, caja.",
    },
    {
        "name": "sync",
        "description": (
            "Replicación con el hub local de sucursal (ADR-009): catálogo y RBAC "
            "hacia el hub, ventas y cobros del corte hacia la nube."
        ),
    },
]


def create_app() -> FastAPI:
    """Crea la aplicación y registra los routers de cada módulo activo."""
    configurar_logging()
    iniciar_sentry("api")
    # En producción no se publica el mapa de la API (esquemas y permisos).
    docs_url = None if settings.es_produccion else "/docs"
    app = FastAPI(
        title="Provecho ERP",
        version=settings.app_version,
        description=(
            "ERP modular para grupo de restaurantes multi-marca. "
            "Convenciones de la API: docs/engineering/api-guidelines.md."
        ),
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=None if settings.es_produccion else "/openapi.json",
        openapi_tags=TAGS_METADATA,
    )

    # Errores de negocio → 4xx, en un solo lugar. Primero el genérico y
    # después el de users: da igual el orden de registro (Starlette resuelve
    # por MRO), pero se lee mejor de lo general a lo particular.
    error_handlers.registrar(app)
    users_error_handlers.registrar(app)

    @app.exception_handler(FueraDeAlcance)
    async def fuera_de_alcance(request: Request, exc: FueraDeAlcance):
        """ADR-004: pedir datos de otro tenant es 403, en cualquier módulo.
        Se resuelve acá y no en cada router para que agregar un endpoint no
        pueda olvidarse de mapearlo."""
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def error_no_controlado(request: Request, exc: Exception):
        """Registra el fallo con su `request_id` y se lo devuelve al cliente:
        sin ese identificador, un reporte de usuario ("me dio error") no se
        puede cruzar con ningún log.

        Se lee de `request.state` y no del contextvar: este handler corre en
        el middleware de errores de Starlette, por fuera de los nuestros.
        """
        rid = getattr(request.state, "request_id", None)
        log.exception(
            "Error no controlado",
            extra={"ruta": request.url.path, "metodo": request.method, "request_id": rid},
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Error interno", "request_id": rid},
            headers={"X-Request-ID": rid} if rid else None,
        )

    @app.middleware("http")
    async def cabeceras_de_seguridad(request: Request, call_next):
        respuesta = await call_next(request)
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        if settings.es_produccion:
            # Solo en producción: en local fijaría https para localhost.
            respuesta.headers["Strict-Transport-Security"] = (
                f"max-age={settings.hsts_max_age_segundos}; includeSubDomains"
            )
        return respuesta

    # Starlette aplica el último agregado como el más externo: TrustedHost
    # rechaza un Host falsificado antes de que el request llegue a nada más.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    # El más externo de los nuestros: así el log de acceso ve el estado
    # final, incluido un rechazo de TrustedHost o de CORS.
    @app.middleware("http")
    async def correlacion_y_acceso(request: Request, call_next):
        """Asigna un `request_id` a cada request y registra cómo terminó.

        Respeta el `X-Request-ID` entrante para poder seguir una traza que
        ya venía del proxy o del frontend.
        """
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = rid
        request_id_var.set(rid)
        inicio = time.perf_counter()
        respuesta = await call_next(request)
        respuesta.headers["X-Request-ID"] = rid
        if request.url.path not in RUTAS_SIN_LOG:
            log.info(
                "%s %s → %s",
                request.method,
                request.url.path,
                respuesta.status_code,
                extra={
                    "metodo": request.method,
                    "ruta": request.url.path,
                    "estado": respuesta.status_code,
                    "duracion_ms": round((time.perf_counter() - inicio) * 1000, 1),
                },
            )
        return respuesta

    app.include_router(health_router)
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(inventory_router, prefix="/api/v1")
    app.include_router(sales_router, prefix="/api/v1")
    app.include_router(kds_router, prefix="/api/v1")
    app.include_router(purchases_router, prefix="/api/v1")
    app.include_router(production_router, prefix="/api/v1")
    app.include_router(accounting_router, prefix="/api/v1")
    app.include_router(rrhh_router, prefix="/api/v1")
    app.include_router(marketing_router, prefix="/api/v1")
    app.include_router(sync_router, prefix="/api/v1")
    inventory_listeners.register()
    accounting_listeners.register()
    marketing_listeners.register()
    return app
