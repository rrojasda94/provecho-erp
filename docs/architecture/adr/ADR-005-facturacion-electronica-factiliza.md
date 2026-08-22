# ADR-005 — Facturación electrónica: Factiliza

- Estado: aceptado
- Fecha: 2026-07-26
- Reemplaza: la suposición de **Nubefact** que arrastraba la documentación
  desde 2026-07-04 sin haberse decidido nunca en un ADR.

## Contexto

En Perú toda venta exige comprobante electrónico validado por SUNAT
(RN-COM-003). Emitir contra SUNAT en directo obliga a mantener certificado
digital, firma XML-DSig, empaquetado UBL 2.1 y el ciclo de CDR — trabajo que
no aporta nada al negocio de restaurantes y que hay que rehacer con cada
cambio normativo. Por eso desde el inicio se asumió un PSE (Proveedor de
Servicios Electrónicos) intermediario.

La documentación nombraba a **Nubefact** en trece archivos, pero esa elección
nunca pasó por un ADR: era un supuesto heredado del scaffold inicial. Al
llegar el momento de implementar, el negocio evaluó y eligió otro proveedor.

## Decisión

**Factiliza** como PSE (decisión del negocio, 2026-07-26).

Motivos:

- El grupo ya lo tiene contratado para otras necesidades, así que no suma
  proveedor ni contrato nuevo.
- Su API cubre en un mismo contrato lo que el ERP necesita por fases:
  `invoice/send` (boleta y factura), `note/send` (nota de crédito y débito),
  `despatch-*` (guía de remisión) y recuperación de PDF/XML/CDR. *Nota
  2026-08-05*: la guía va en `sales` junto al resto de comprobantes, no en
  un módulo `logistics` — el despacho ya vive en `inventory` (ADR-020) y la
  guía es el comprobante que lo acompaña, no un dominio aparte.
- Autenticación por Bearer token estático, sin flujo OAuth que mantener.
- Expone además APIs de consulta (RUC, DNI, tipo de cambio) que sirven al
  alta de proveedores y clientes sin integrar otro servicio.

## Consecuencias

- Adaptador único en `src/shared/integrations/factiliza/`: `client.py`
  (transporte HTTP) y `mapper.py` (traducción del dominio a los catálogos
  SUNAT 01/06/07/51/52). El dominio de `sales` no conoce Factiliza — sigue la
  regla de CLAUDE.md de que ninguna integración se llama desde el dominio.
- La consulta RUC/DNI (`FactilizaClient.consultar_dni`/`consultar_ruc`,
  2026-08-02) vive en un **host distinto** al de emisión: `api.factiliza.com`
  (`FACTILIZA_CONSULTA_BASE_URL`), no `apife-qa.factiliza.com`
  (`FACTILIZA_BASE_URL`) — son productos separados de Factiliza, que se
  contratan y se cobran por separado y tienen **una credencial cada uno**
  (`FACTILIZA_CONSULTA_DOCUMENTO_TOKEN`, 2026-08-22). Vacío, se reusa
  `FACTILIZA_TOKEN`: un plan que cubra ambos con un solo token no configura
  nada. Se sostienen aparte porque cruzarlos falla de forma cara y muda —el
  token de emisión contra el host de consulta da 401, y el buscador de DNI
  del mostrador muere con un 502 genérico— y porque rotar uno no puede
  apagar el otro. La consulta no tiene sandbox QA propio: la prueba con
  datos reales (DNI 73632127, RUC 20610077782) se hizo contra ese único
  host. `nombres_desde_dni`/`razon_social_desde_ruc` envuelven la consulta
  con el mismo criterio de "nunca bloquear": sin respuesta o documento no
  encontrado, cae a lo tecleado por el usuario. Cableado en el alta de
  cliente (`sales`) y proveedor jurídico (`purchases`) — ver RN-PTS-004 en
  `docs/domain/business-rules.md`.
- El mapper es la pieza que **no** es reutilizable si se cambia de proveedor:
  los catálogos SUNAT sí son estándar, pero el nombre y la forma de cada
  campo son de Factiliza. El `client.py` sí es intercambiable.
- Emisión **asíncrona** por Celery (ver ADR-006): la caja nunca espera a
  SUNAT. Un rechazo de SUNAT se guarda como veredicto y no se reintenta —
  el dato está mal, reintentar no lo arregla. Un fallo de transporte sí
  reintenta con espera exponencial.
- Sin `FACTILIZA_TOKEN` la emisión queda desactivada y los comprobantes se
  acumulan en estado `pendiente`. **La venta jamás se bloquea** (RN-COM-003):
  un restaurante no puede dejar de cobrar porque un proveedor externo esté
  caído.
- Las columnas `comprobante.estado_nubefact`/`respuesta_nubefact` se
  reemplazaron por nombres agnósticos (`estado_emision`, `hash_proveedor`,
  `detalle_emision`, `intentos_emision`, `respuesta_proveedor`) en la
  migración `b3d7f21ac094`, para no volver a atar el esquema al nombre de un
  proveedor.

## Alternativas descartadas

- **Nubefact** — supuesto previo, nunca decidido formalmente. Descartado por
  la decisión del negocio a favor de un proveedor ya contratado.
- **Integración directa con SUNAT** — descartada: obliga a mantener
  certificado digital, firma y UBL dentro del ERP, con reescritura en cada
  cambio normativo. Es el problema que un PSE existe para resolver.
