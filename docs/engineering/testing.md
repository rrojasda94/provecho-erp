# Testing

Desde el inicio. Todo cambio lleva sus pruebas en el mismo commit.
CI ejecuta todo antes de aceptar cambios.

## Niveles

| Nivel | Qué prueba | Herramienta |
|-------|-----------|-------------|
| Unitario | Clases/funciones aisladas (dominio, casos de uso) | pytest |
| Integración | Repositorios contra PostgreSQL, endpoints con TestClient | pytest + httpx |
| E2E | Recorridos completos (login → venta → stock) | por definir al tener UI |

Frontend: lint + build en CI; tests de componentes al crecer la UI.

## Datos de prueba

- **Factories** para entidades de dominio (crear al implementar cada módulo).
- **Fixtures** pytest para sesión de DB transaccional (rollback por test).
- **Seeders** para entornos de desarrollo: usuario `admin`/PIN `123456`,
  organización base (grupo, empresa, marcas, sucursales). Prohibidos en producción.

## Convenciones

- Tests en `tests/`, espejo de `src/` (`tests/modules/inventory/...`).
- Nombre descriptivo: `test_<caso>_<resultado>` — ej.
  `test_transferencia_no_despacha_mas_de_lo_aprobado`.
- El dominio se prueba sin DB (repositorios falsos); la infraestructura con DB real.
- Cobertura razonable > cobertura total: prioridad a reglas de negocio y dinero.
