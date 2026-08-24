# Módulo `marketing` — Marca, contenido y campañas

**Estado (2026-08-08):** slice core (2026-08-01, migración `e9c3b7412a68`)
+ **slice encuesta/agencia/métricas** (migración `c1f80b6a2d34`,
ADR-029/030): envío real de la encuesta por WhatsApp con guion ramificado,
calendario de contenido con adjuntos, evaluación de agencia y consumidores
para los eventos propios. Lo que queda fuera está en `ROADMAP.md` → Deuda
técnica → marketing.

## Objetivo

Gestionar el crecimiento de marca: campañas con objetivo medible,
contenido pertinente a la marca, naming, material en sucursal, y la
atribución lead→venta en conjunto con `sales`/Comercial.

## Entidades

`campana` (tipo, objetivo, público, canal, presupuesto, KPI, estado,
aprobación gerencial si sobre umbral), `pieza_contenido` (calendario,
pertinencia y uso de marca validados, **arte adjunto vía `archivo`**),
`lead` (canal, atribución a `venta_id`),
`implementacion_material_sucursal` (verificación en sitio),
`evaluacion_agencia` + `opcion_agencia` (RN-MKT-006),
`campana_metrica` (acumulado por eventos).

`encuesta_satisfaccion` pertenece a este módulo (spec en
`docs/architecture/data-model.md` §6 y §8d), junto con su guion
(`encuesta_plantilla`, `encuesta_pregunta`) y el detalle de lo contestado
(`encuesta_respuesta`). Su disparador es `sales.venta_entregada`, que emite
`PROC-OPE-002` (Cumplimiento de pedido). Marketing elige a qué venta
entregada enviarle encuesta (selectiva, RN-COM-007) y al enviarla emite
`marketing.encuesta_enviada`.

`contrato` (transversal) y las compras de material (`purchases`) no se
duplican aquí — Marketing las usa.

## La encuesta es una conversación, no un formulario (ADR-029)

El canal principal es WhatsApp, donde no hay formulario: hay mensajes, uno a
la vez. Por eso el guion es un **grafo de nodos** y la fila de la encuesta
recuerda en cuál está el cliente.

- Cada `encuesta_pregunta` declara `siguiente_codigo` (camino normal) y
  `saltos` (`{"2": "que_fallo"}`, desvío por la respuesta). Un 2 de 5
  pregunta qué falló; un 5 pregunta si nos recomendaría.
- El guion se valida entero al guardarlo: saltos rotos y ciclos se rechazan
  ahí, no a mitad de conversación con el cliente esperando.
- Una plantilla activa por empresa. El seeder trae una de fábrica.
- `puntaje` y `comentario` **siguen existiendo** en `encuesta_satisfaccion`:
  se llenan desde el nodo `es_puntaje` y el último texto libre, así que quien
  ya los leía (reportes, tablero) no cambió.

### Secuencia real por WhatsApp

1. **Apertura**: plantilla aprobada de Meta (`WHATSAPP_PLANTILLA_ENCUESTA`)
   con el nombre del cliente y el enlace público. Fuera de la ventana de
   24 h, Meta no acepta otra cosa.
2. El cliente contesta cualquier cosa → se abre la ventana. **Ese mensaje no
   es una respuesta** (`conversacion_abierta`): recién ahí sale la primera
   pregunta. Contarlo como puntaje dejaría a media base con la nota de haber
   dicho que sí.
3. Cada respuesta avanza un nodo y dispara la siguiente pregunta, hasta la
   despedida.

Tres puertas de entrada, **un solo caso de uso**
(`encuestas.responder_nodo`): el webhook de Meta, el enlace público y
`POST /encuestas/{id}/respuesta` (la tablet del local, canal `pos`).

## Endpoints

| Recurso | Endpoints | Permiso |
|---|---|---|
| Campaña | `POST/GET /campanas`, `GET /campanas/{id}`, `PATCH /campanas/{id}/brief`, `POST /campanas/{id}/{aprobacion,lanzamiento,cierre}` | `marketing.campana_gestionar`, aprobación con `marketing.campana_aprobar` |
| Métricas | `GET /campanas/{id}/metricas`, `POST /campanas/{id}/metricas/recalculo` | `marketing.leer` / `marketing.campana_gestionar` |
| Material en sucursal | `POST /campanas/{id}/implementaciones` | `marketing.campana_gestionar` |
| Contenido | `POST /piezas`, `GET /piezas` (filtra `estado`, `desde`, `hasta`), `GET /piezas/calendario`, `PATCH /piezas/{id}/validacion`, `POST /piezas/{id}/{publicacion,descarte}` | `marketing.contenido_gestionar` |
| Adjuntos de pieza | `POST/GET /piezas/{id}/adjuntos`, `DELETE /piezas/{id}/adjuntos/{archivo_id}` | `marketing.contenido_gestionar` (lectura con `marketing.leer`) |
| Lead | `POST /leads`, `GET /campanas/{id}/leads`, `POST /leads/{id}/atribucion` | `marketing.lead_gestionar` |
| Guion de encuesta | `POST/GET /encuestas/plantillas`, `GET /encuestas/plantillas/{id}`, `POST /encuestas/plantillas/{id}/activacion` | `marketing.encuesta_gestionar` |
| Encuesta | `POST /encuestas`, `GET /encuestas/{id}`, `POST /encuestas/{id}/{respuesta,expiracion}` | `marketing.encuesta_gestionar` |
| Evaluación de agencia | `POST/GET /campanas/{id}/evaluaciones-agencia`, `GET /evaluaciones-agencia/{id}`, `POST /evaluaciones-agencia/{id}/{opciones,cierre}` | `marketing.agencia_evaluar` |
| Decisión de agencia | `POST /evaluaciones-agencia/{id}/decision` | `marketing.agencia_decidir` |
| **Público (sin JWT)** | `GET/POST /marketing/publico/encuestas/{token}` | token del enlace + rate limit |
| **Webhook (sin JWT)** | `GET/POST /webhooks/whatsapp` | firma HMAC de Meta + rate limit |

Lectura general con `marketing.leer`. El rol semilla `marketing` no lleva
`marketing.campana_aprobar` ni `marketing.agencia_decidir`: quien escribe el
brief no lo aprueba y quien arma la comparación no la firma (RN-MKT-003,
RN-MKT-006, RN-GER-007) — esos dos permisos viven en `supervisor`.

Los errores de aplicación heredan de `src/shared/errors.py`; el mapeo a HTTP
vive una sola vez en `src/core/error_handlers.py` (los routers no traducen).

## Alcance de tenant (ADR-004)

`campana` lleva `empresa_id` propio y es la raíz del alcance: pieza, lead,
implementación de material y evaluación de agencia se validan por su
campaña. `encuesta_plantilla` lleva `empresa_id` propio. La encuesta se
escopa por la sucursal de su venta, leída por el contrato público de
`sales` — marketing nunca importa `Venta`.

Las dos superficies **sin JWT** no usan tenant y no pueden: el cliente que
contesta no es usuario del ERP. Traen su propia credencial (token del enlace,
firma HMAC) y devuelven lo mínimo — nunca la venta, el cliente ni el monto.

## Casos de uso

- Crear campaña con brief; no pasa de `brief` a `aprobada` sin objetivo,
  público, presupuesto y KPI (RN-MKT-003); gasto fuera del presupuesto
  anual o sobre el límite genera una `decision_gerencial` (RN-GER-007/003).
- Planificar calendario de contenido **con el arte adjunto**; publicar solo
  piezas marcadas pertinentes y con uso de marca validado (RN-MKT-001/002).
- Definir/validar naming de producto o campaña (RN-MKT-007).
- Registrar leads de campaña y atribuirlos a la venta real cuando
  Comercial cierra (mide conversión, no solo alcance).
- Verificar la implementación de material en cada sucursal —producto
  nuevo y clásico— (RN-MKT-005).
- Evaluar propuesta de agencia vs. interna contra objetivo y presupuesto
  (RN-MKT-006) — Marketing evalúa, Gerencia valida; se formaliza por
  `contrato` y paga Contabilidad, la agencia (servicio) no pasa por
  `purchases`.
- Enviar la encuesta a una venta entregada y conducirla nodo por nodo hasta
  el final (RN-COM-007).

## Reglas

- Sin brief aprobado, la campaña no sale a canal (RN-MKT-003).
- Contenido no pertinente a la marca no se publica, aunque sea viral
  (RN-MKT-002).
- Marketing no modifica la identidad de la marca (reservado, RN-MAR-004);
  solo asegura su buen uso (RN-MKT-001).
- El **material** (bien) se adquiere vía `purchases`, no por fuera
  (RN-MKT-004); la **agencia** (servicio) la evalúa Marketing y la valida
  Gerencia, vía `contrato` + Contabilidad, no `purchases` (RN-MKT-006).
- Una evaluación de agencia no se cierra sin la opción **interna**
  compitiendo, y apartarse de la recomendada o del presupuesto exige motivo
  escrito (RN-MKT-006, RN-GER-003).
- Enviar material no cierra la tarea: se verifica la implementación en
  sucursal (RN-MKT-005).
- La encuesta es selectiva: nunca automática para toda venta (RN-COM-007).

## Flujo

Objetivo (con Comercial si es venta) → brief aprobado → (naming + uso de
marca validados) → material vía Compras + agencia evaluada y decidida →
lanzamiento → leads registrados → atribución lead→venta con `sales` →
encuesta a los clientes que la campaña trajo → cierre y medición
(`GET /campanas/{id}/metricas`).

## Relaciones

- Escucha de `sales`: `sales.cliente_registrado_en_promocion` → crea el `lead`
  de quien se registró en la landing pública del QR (tipo `registro`, canal
  `qr`, ADR-061). Empareja **por nombre** con una campaña `en_curso`: el cupón
  vive en `sales` y marketing no puede leer `promocion_cupon`. Sin campaña
  abierta con ese nombre no hay lead, y está bien — el lead es cómo Marketing
  mide, no parte de lo que se le prometió al cliente; frenar el registro por
  un brief sin abrir lo dejaría sin su cupón.
- Escucha de `sales`: `sales.venta_confirmada` → atribuye la venta a un
  `lead` (`application/listeners.py`) **solo si no hay ambigüedad**: el
  cliente tiene exactamente un lead abierto en una campaña en curso. Con dos
  o más, adivinar cuál campaña convirtió falsearía la medición — esos casos
  van por `POST /leads/{id}/atribucion`. Requiere `cliente_id` en el payload
  del evento.
- **Escucha lo propio** (ADR-030): `campana_lanzada`, `lead_generado`,
  `lead_atribuido`, `pieza_publicada`, `encuesta_enviada` y
  `encuesta_respondida` alimentan `campana_metrica`; `encuesta_enviada`
  además encola el envío real por WhatsApp. Hasta 2026-08-08 estos eventos
  se publicaban al vacío.
- Publica: los seis de arriba más `marketing.agencia_decidida`.
- Lee por contrato público de `sales`: `venta_para_encuesta` (entrega y
  sucursal) y `contacto_de_cliente` (teléfono para el WhatsApp).
- Coordina (no vía evento): `purchases` (material), `production`
  (disponibilidad de producto nuevo, RN-CML-005), `accounting`
  (presupuesto), Gerencia (aprobación sobre umbral).

## Tareas en segundo plano

- `marketing.despachar_encuesta` — manda el mensaje que toque (plantilla,
  pregunta o despedida). Reintenta con backoff ante fallo de transporte; un
  rechazo de Meta (4xx) **no** reintenta y queda en `error_envio`.
- `marketing.barrer_encuestas_vencidas` — Celery beat, cada hora. Expira lo
  que superó `MARKETING_ENCUESTA_VIGENCIA_HORAS` (72 por defecto).

## Configuración

`WHATSAPP_BASE_URL`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TOKEN`,
`WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, `WHATSAPP_TIMEOUT_SEGUNDOS`,
`WHATSAPP_PLANTILLA_ENCUESTA`, `WHATSAPP_PLANTILLA_IDIOMA`,
`MARKETING_ENCUESTA_VIGENCIA_HORAS`, `MARKETING_URL_PUBLICA`.

Sin `WHATSAPP_TOKEN` el módulo funciona igual: la encuesta se crea y se
contesta por el enlace público o la tablet, y no se encola ningún envío.
En producción, `WHATSAPP_TOKEN` sin `WHATSAPP_APP_SECRET` impide arrancar.
