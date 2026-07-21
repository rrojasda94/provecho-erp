# Módulos

La especificación de cada módulo vive en su `README.md`
(objetivo, responsabilidades, casos de uso, eventos, API, entidades, reglas,
dependencias) y se escribe ANTES de implementar. Mapa de eventos:
[../diagrams/modules.md](../diagrams/modules.md) ·
catálogo: [../architecture/events.md](../architecture/events.md).

## Activos (F0 — especificados)

| Módulo | Especificación | Estado |
|--------|----------------|--------|
| users | [src/modules/users/README.md](../../src/modules/users/README.md) | Spec lista, implementación pendiente |
| inventory | [src/modules/inventory/README.md](../../src/modules/inventory/README.md) | Spec lista |
| sales | [src/modules/sales/README.md](../../src/modules/sales/README.md) | Spec lista |
| purchases | [src/modules/purchases/README.md](../../src/modules/purchases/README.md) | Spec lista |
| accounting | [src/modules/accounting/README.md](../../src/modules/accounting/README.md) | Abierto parcialmente (ciclo de caja), spec completa pendiente |
| rrhh | [src/modules/rrhh/README.md](../../src/modules/rrhh/README.md) | Abierto parcialmente (solo `trabajador`), spec completa pendiente |

## Futuros (se especifican antes de construirse)

production (fabricación), requests/logistics (solicitudes, picking,
transporte), caja, rrhh, crm, tesorería, activos, proyectos, bi/reportes,
supervisión, settings (ajustes/branding por marca).

## Reglas

- Un módulo = una carpeta autocontenida en `src/modules/`.
- Se activa registrando su router y sus handlers de eventos en `core`;
  se desactiva no registrándolos.
- Comunicación entre módulos SOLO por eventos o contratos públicos.
- Cada módulo trae sus tests, sus migraciones y su README actualizado.
- Si el README crece demasiado, se expande a `src/modules/<módulo>/docs/`
  junto al código — nunca a un árbol paralelo en `docs/`.
