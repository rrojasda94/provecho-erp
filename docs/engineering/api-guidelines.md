# Convenciones de API

API REST bajo `/api/v1/`. Documentación OpenAPI/Swagger generada automática
por FastAPI en `/docs` — siempre sincronizada con el código (se genera de él).

## Reglas

- **Validación total**: no confiar en el cliente. Todo endpoint valida tipos,
  longitud, formato (Pydantic) y reglas de negocio (dominio).
- **Idempotencia**: operaciones críticas (pagos, compras, facturación, venta)
  reciben header `Idempotency-Key`; reintentos no duplican efectos.
- **Versionado**: prefijo `/api/v1`; cambios incompatibles → `/api/v2`.
- **Autenticación**: `Authorization: Bearer <JWT>` en todo endpoint salvo
  login/refresh y `/health`.
- **Tenant**: el contexto (empresa/marca/sucursal) sale de los claims del
  JWT + parámetros validados contra las asignaciones del usuario — nunca
  del body sin verificar.

## Formato de respuestas

- Éxito: JSON del recurso; colecciones paginadas
  `{items, total, page, page_size}`.
- Error: `{detail}` (FastAPI) con código HTTP correcto:
  `400` validación, `401` sin auth, `403` sin permiso, `404` no existe,
  `409` conflicto/idempotencia, `422` reglas de negocio.
- Fechas ISO 8601 UTC. Montos como decimal en string (nunca float).

## Nomenclatura

Recursos en plural y español, kebab-case en rutas
(`/api/v1/ordenes-compra/{id}/recepciones`), snake_case en JSON.
