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

## El suite no sale a internet

Ninguna prueba de `pytest` toca la red: las integraciones externas se prueban
con dobles de `httpx`. Un suite que depende de que SUNAT esté arriba deja de
significar "el código está mal", que es lo único que un suite sirve para decir
— y de paso quema cuota de un proveedor pago en cada corrida del CI.

La excepción está marcada `red` y **excluida por `addopts`**, así que `pytest`
a secas —lo que corre el CI— nunca la ejecuta. Se dispara a mano desde la raíz
del repo, que es donde vive el `.env` con los tokens:

```bash
pytest -m red
```

Hoy son las consultas RUC/DNI contra Factiliza (`tests/test_factiliza_red.py`),
y **solo consultas**: emitir por red generaría un comprobante real ante SUNAT.
Sin token configurado, esas pruebas quedan `skipped`, no rojas.

Una prueba de red no puede pedirle datos a terceros para armar su aserción. La
versión "consultar un DNI que no exista" se descartó por eso: dar con uno
obliga a consultar documentos de desconocidos hasta que alguno falle. Ese caso
se prueba con dobles.

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
