# Contexto para escribir tests

Leer antes: [engineering/testing.md](../engineering/testing.md).

## Reglas duras

- Todo cambio de comportamiento lleva test en el mismo commit.
- Dominio se prueba aislado (sin DB, repositorios falsos); infraestructura
  contra PostgreSQL con rollback por test; endpoints con TestClient.
- Nombres descriptivos: `test_<caso>_<resultado_esperado>`.
- Factories para entidades; seeders solo para entornos de desarrollo.
- Prioridad: reglas de negocio y flujos de dinero (venta, pago, stock).

## Ejecutar

```bash
pytest            # todo
pytest tests/modules/inventory  # un módulo
```
