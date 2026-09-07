# ADR-090 — La guía de remisión se emite desde su documento origen

- Estado: aceptado
- Fecha: 2026-09-06
- Contexto: `src/modules/inventory/api/routers.py`,
  `src/modules/inventory/application/guias.py`,
  `src/shared/integrations/factiliza/client.py`,
  `src/shared/integrations/factiliza/guias.py`,
  `src/modules/inventory/infrastructure/models/unidad_medida.py`,
  `frontend/app/(app)/inventario/transferencias/`,
  `frontend/app/(app)/inventario/devoluciones/`,
  `frontend/app/(app)/inventario/guias-remision/`
- Relacionado: ADR-027 (guía de remisión), ADR-005 (Factiliza), ADR-048 (el
  proxy pasa bytes)

## Contexto

ADR-027 dejó el backend completo el 2026-08-05: `POST/GET
/transferencias/{id}/guia`, `GET /guias-remision`, `POST
/devoluciones/{id}/guia-remision`, un permiso propio
(`inventory.emitir_guia`) y 14 pruebas. El 2026-09-04 quedó anotado en
`docs/roadmap/deuda/modulo-inventory.md` que ninguna pantalla los llamaba —
el mismo patrón que la auditoría del 2026-08-30 vino a cortar en el resto
del ERP.

Junto con eso quedaban dos huecos menores: la descarga de PDF/XML/CDR de una
guía aceptada apuntaba al mismo cliente HTTP que el comprobante pero con la
ruta hardcodeada a `/invoice/...` (la de la guía es `/despatch/...`), y el
mapeo de unidad de medida a su código SUNAT vivía solo en un diccionario de
doce entradas con `NIU` de fallback silencioso.

## Decisión

**El botón de emitir vive en el documento que la guía declara, no en una
pantalla propia.** RN-TRP-002 exige que lo transportado coincida
exactamente con lo que salió del almacén — un formulario de guía aparte
sería la forma de que no coincidan. Por eso «Guía» aparece como una acción
más en la fila de Traslados y, cuando `origen=proveedor` y
`estado=registrada`, en la fila de Devoluciones. La lista
`/inventario/guias-remision` es de **solo lectura**: sirve para revisar lo
ya emitido y encontrar rápido lo `rechazado`, no para emitir.

**El diálogo pregunta primero si ya existe una guía.** `GET
.../guia`/`GET .../guia-remision` es idempotente por documento origen — la
misma pregunta que ya resolvía el backend al emitir (RN-GDR-001..003):
pedirla dos veces no numera una segunda. La devolución no tenía ese `GET`
—solo el `POST`, cuyo cuerpo de éxito ya trae la guía—, así que este bloque
sumó `GET /devoluciones/{id}/guia-remision`, simétrico al de transferencia
y con el mismo caso de uso `de_devolucion` que el repositorio ya exponía
para la idempotencia interna.

**La descarga generaliza el cliente de comprobantes en vez de duplicarlo.**
`FactilizaClient.descargar` gana un parámetro `recurso: "invoice" |
"despatch"` con default `"invoice"` — mismo verbo, mismo formato de
respuesta, solo cambia el prefijo del path. `TIPO_DOC_GUIA_REMITENTE = "09"`
ya existía en `guias.py`. El endpoint nuevo,
`GET /guias-remision/{id}/descargar/{formato}`, es una copia deliberada de
`sales.descargar_comprobante`: mismo criterio de "solo se descarga lo
aceptado, se pide al proveedor en el momento y no se archiva".

**`codigo_sunat` es una columna, no un segundo diccionario.** Nullable en
`unidad_medida`, editable desde los endpoints de Catálogo que ya existían
(`POST/PATCH /inventory/unidades-medida[/{id}]`). `codigo_unidad()` la usa
primero si está configurada; el diccionario de doce entradas sigue de
fallback para lo que nadie configuró todavía y de valor de siembra — no se
borra, se degrada a segundo lugar.

## Descartado en este bloque

**La anulación por comunicación de baja no se implementó.** El payload de
`/despatch/send` (envío) nunca se verificó contra el sandbox de QA real de
Factiliza, y esta sesión no tenía `FACTILIZA_TOKEN` ni acceso de red al
proveedor para hacerlo con criterio — construir la anulación a ciegas,
adivinando el contrato de un endpoint que nunca se vio responder, es
exactamente el error que la boleta evitó al no emitirse hasta probarse
contra QA (ADR-005). Queda igual que estuvo la descarga hasta este bloque:
anotada en `docs/roadmap/deuda/modulo-inventory.md`, pendiente de quien
tenga el token de QA puesto.

## Consecuencias

- `inventory.emitir_guia` (sembrado en `almacenero` desde ADR-027) por fin
  se ejerce desde una pantalla.
- La descarga de una guía sigue el mismo patrón que la de un comprobante:
  un cambio en uno alerta a revisar el otro.
- Una UdM sin `codigo_sunat` configurado sigue funcionando exactamente
  igual que antes de este bloque — el cambio es aditivo y no exige
  migración de datos existentes.
