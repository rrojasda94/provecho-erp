# Convenciones de API

API REST bajo `/api/v1/`. Documentación OpenAPI/Swagger generada automática
por FastAPI en `/docs` (deshabilitada en producción, ver `security.md`) —
siempre sincronizada con el código porque se genera de él, nunca a mano.

**Contrato exportado**: `docs/architecture/openapi.json`
(`python -m src.core.openapi_export`), para que Android/PC/integraciones
generen su SDK sin necesitar un servidor corriendo. CI lo regenera y lo
compara contra el commiteado — un endpoint que cambió sin dejar el contrato
al día falla el PR que lo causó (ADR-010).

## Reglas

- **Validación total**: no confiar en el cliente. Todo endpoint valida tipos,
  longitud, formato (Pydantic) y reglas de negocio (dominio).
- **Idempotencia**: operaciones críticas (venta, pago, facturación, compra)
  reciben `idempotency_key` como **campo del body** (no header — corregido
  2026-07-26, esta guía decía "header" pero el código siempre lo pidió en
  el JSON); reintentos con la misma clave devuelven el recurso ya creado, no
  duplican efectos.
- **Versionado**: prefijo `/api/v1`; cambios incompatibles → `/api/v2`.
- **Autenticación**: `Authorization: Bearer <JWT>` en todo endpoint salvo
  login/refresh y `/health` y sus variantes (`/health/ready`,
  `/health/backups`, `/health/sync`) — deliberadamente públicos para que un
  monitor externo los sondee sin credenciales (ver ADR-007).
- **Tenant**: el contexto (empresa/marca/sucursal) sale de los claims del
  JWT + parámetros validados contra las asignaciones del usuario — nunca
  del body sin verificar.

## Formato de respuestas

- Éxito: JSON del recurso. Las colecciones hoy devuelven un array plano
  (`list[Schema]`), **no** el sobre `{items, total, page, page_size}` — esta
  guía lo afirmaba sin que ningún endpoint lo implementara (corregido
  2026-07-26). Paginación real es deuda técnica, a construir cuando una
  colección lo justifique (ver ROADMAP); hasta entonces, documentar acá el
  formato real evita que un cliente externo codifique contra un contrato
  que no existe.
- Error: `{detail}` (FastAPI) con código HTTP correcto:
  `400` validación, `401` sin auth, `403` sin permiso, `404` no existe,
  `409` conflicto/idempotencia, `422` reglas de negocio.
- Fechas ISO 8601 UTC. Montos como decimal en string (nunca float).

## Nomenclatura

Recursos en plural y español, kebab-case en rutas
(`/api/v1/ordenes-compra/{id}/recepciones`), snake_case en JSON.

## Tags de OpenAPI

Cada router declara su tag (`accounting`, `sales`, `kds`, etc.) y
`TAGS_METADATA` en `src/core/app.py` le agrega descripción — un tag nuevo
sin entrada ahí queda sin explicación en `/docs` y en el contrato exportado
(`tests/test_openapi_export.py` lo verifica). Al agregar un router con tag
nuevo, sumar su descripción en `TAGS_METADATA` en el mismo cambio.
