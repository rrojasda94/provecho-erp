# ADR-029 — Encuesta de satisfacción por nodos y canal WhatsApp

- Estado: aceptado
- Fecha: 2026-08-08

## Contexto

El slice core de `marketing` (ADR-021) dejó la encuesta de satisfacción como
una fila con `puntaje` y `comentario`: `POST /encuestas` la creaba, publicaba
`marketing.encuesta_enviada` y ahí terminaba. **Nada salía del ERP.** El
ROADMAP lo declaraba como deuda: "Encuesta sin envío real ni expiración
automática — mandar el WhatsApp/link es trabajo de un adaptador en
`src/shared/integrations/` que todavía no existe".

Al ir a construir ese adaptador aparecieron cuatro decisiones que el diseño
anterior no podía sostener.

**1. Un formulario no cabe en WhatsApp.** El canal no tiene formulario:
tiene una conversación, un mensaje a la vez. Con `puntaje` y `comentario`
como columnas sueltas, una respuesta que llega tres horas después no se
puede interpretar — no hay forma de saber si ese "no" es el puntaje, el
comentario o un mensaje suelto.

**2. Preguntarle lo mismo a todos no sirve.** Quien puntúa 2 tiene que decir
**qué** falló; quien puntúa 5 puede decir si nos recomendaría. Preguntarles
las dos cosas a todos alarga la encuesta y baja la tasa de respuesta, que es
la única métrica que hace que el resto sirva.

**3. La ventana de 24 h de Meta.** Fuera de una conversación abierta por el
cliente, la WhatsApp Cloud API **solo** acepta plantillas aprobadas. No es un
detalle de implementación: cambia la secuencia del negocio, porque el primer
mensaje no puede ser la primera pregunta.

**4. El cliente no es usuario del ERP.** No tiene cuenta, no puede tener
JWT, y el webhook lo llama Meta, no una persona.

## Decisión

**1. El guion de la encuesta es dato, no código.** `encuesta_plantilla` +
`encuesta_pregunta`. Cada pregunta es un **nodo** que declara a dónde sigue
la conversación: `siguiente_codigo` es el camino normal y `saltos`
(`{"2": "que_fallo"}`) lo desvía según la respuesta. Marketing cambia el
orden, agrega una pregunta o corta una rama sin desplegar.

El destino se guarda por `codigo` y no por id: una plantilla se escribe y se
lee de corrido, y agregar un nodo en medio no obliga a conocer UUID que
todavía no existen.

**2. `encuesta_satisfaccion` guarda el estado de la conversación.**
`plantilla_id` + `pregunta_actual_id` dicen en qué nodo está el cliente;
`encuesta_respuesta` guarda el detalle nodo por nodo. `puntaje` y
`comentario` **siguen existiendo** como el resumen que consume el negocio
(reportes, tablero): se llenan desde el nodo marcado `es_puntaje` y desde el
último texto libre. Cambiar el modelo no obligó a reescribir a quien ya
leía esas dos columnas.

**3. Una plantilla activa por empresa.** Activar la nueva desactiva la
anterior. Dos guiones vivos parten la serie histórica en dos mitades que no
se pueden comparar, y nadie se entera hasta que el reporte mensual no cuadra.
El seeder trae una activa de fábrica: sin ella `POST /encuestas` respondería
409 y el módulo llegaría inutilizable a la primera instalación.

**4. El guion se valida entero al guardarlo.** Saltos a nodos inexistentes,
opciones vacías y **ciclos** se rechazan al crear la plantilla, no al
enviar. Un ciclo (A → B → A) no rompe nada al guardar y convierte la
encuesta en un bucle que le escribe al cliente para siempre; un destino roto
lo deja esperando una pregunta que nunca llega. En los dos casos, cuando se
descubre ya no hay a quién avisarle.

**5. La secuencia real por WhatsApp tiene tres tramos.**

1. **Apertura**: plantilla aprobada (`WHATSAPP_PLANTILLA_ENCUESTA`) con el
   nombre del cliente y el enlace público. Es lo único que Meta acepta fuera
   de la ventana.
2. **Apertura de ventana**: el cliente contesta cualquier cosa ("ok", un
   emoji). Ese mensaje **no se interpreta como respuesta** —
   `encuesta_satisfaccion.conversacion_abierta` lo distingue — y recién ahí
   sale la primera pregunta. Contarlo como puntaje dejaría a media base con
   la nota de haber dicho que sí.
3. **Guion**: cada respuesta avanza un nodo y dispara la siguiente pregunta,
   hasta que el guion corta y sale la despedida.

**6. Tres puertas de entrada, un solo caso de uso.** El webhook de WhatsApp,
el enlace público y `POST /encuestas/{id}/respuesta` (la tablet del local,
canal `pos`) llaman todos a `encuestas.responder_nodo`. La regla de qué es
una respuesta válida y cuál es el siguiente nodo vive en un solo lugar.

**7. Autenticación por canal, no por usuario.**
- Enlace público: `token_publico` (32 bytes urlsafe) en la URL. Es una
  credencial anónima, así que la respuesta **no** incluye venta, cliente ni
  monto — quien reenvíe el link no puede leer el pedido.
- Webhook: firma HMAC-SHA256 del **cuerpo crudo** contra
  `WHATSAPP_APP_SECRET`. Sin secreto configurado rechaza todo (fail-closed);
  `settings` no deja arrancar en producción con `WHATSAPP_TOKEN` y sin
  secreto.
- Los dos con rate limit por IP: son las únicas superficies sin JWT del ERP
  fuera del login.

**8. El envío cuelga del evento, no del endpoint.** El listener de
`marketing.encuesta_enviada` encola `marketing.despachar_encuesta`. Gracias a
ADR-016 el evento se despacha recién al commitear, así que el worker
encuentra la fila que va a leer. Los tres `event_bus.publish` que marketing
tenía sin `session=` se corrigieron en el mismo cambio.

**9. Expiración por barrido.** `marketing.barrer_encuestas_vencidas` cada
hora (Celery beat), con vigencia configurable
(`MARKETING_ENCUESTA_VIGENCIA_HORAS`, 72 por defecto). Una respuesta de dos
semanas después no mide la experiencia de ese pedido; y una encuesta
`enviada` para siempre deja el porcentaje de respuesta sin cerrar.

**10. Un rechazo de Meta no se reintenta.** `WhatsAppRechazo` (4xx: número
inválido, plantilla no aprobada) **no** hereda de `WhatsAppError`: queda
escrito en `encuesta_satisfaccion.error_envio` y no vuelve a la cola.
Reenviar el mismo payload da el mismo 400. Solo transporte caído y 5xx
reintentan, con el mismo backoff que la emisión electrónica.

## Alternativas descartadas

**Guardar el guion en código (un `dict` en Python).** Más rápido de escribir
y obliga a un despliegue para cambiar una pregunta. Marketing itera el
cuestionario mucho más seguido que el ERP se despliega; con el guion en
código, cambiarlo deja de ser trabajo de Marketing.

**Un solo endpoint que recibe todas las respuestas juntas.** Es lo natural
para un formulario web y no existe en WhatsApp: no hay "enviar formulario",
hay mensajes sueltos. Habría obligado a un segundo modelo de encuesta para
el canal principal.

**Mandar la primera pregunta como plantilla aprobada.** Evitaría el ida y
vuelta de apertura, pero cada cambio del guion exigiría aprobar una plantilla
nueva en Meta (días de espera) y las respuestas con botones no funcionan
igual en plantillas. La apertura genérica se aprueba una vez y no se toca.

**Enviar en línea desde el request de `POST /encuestas`.** Deja al usuario
del ERP esperando la latencia de Meta y pierde el mensaje si la API está
caída. Con cola hay reintentos y el request vuelve al instante.

**Aceptar el webhook sin firma cuando no hay secreto configurado.** Es lo
cómodo para desarrollo y significa que una instalación a medio configurar
queda con un endpoint público que cualquiera puede usar para contestar
encuestas ajenas. Falla cerrado.

## Consecuencias

- `POST /marketing/encuestas/{id}/respuesta` **cambia de contrato**: recibe
  `{"valor": "..."}` (respuesta a **un** nodo) en vez de
  `{"puntaje": n, "comentario": "..."}`, y devuelve `{encuesta,
  pregunta_actual, url_publica}` en vez de la encuesta pelada. No hay datos
  productivos: el módulo se creó el 2026-08-01 y no hay campañas cargadas.
- Las encuestas anteriores (`plantilla_id` NULL) se siguen contestando con un
  puntaje suelto: la migración no inventa un guion retroactivo.
- Dos endpoints nuevos sin JWT (`/api/v1/marketing/publico/*`,
  `/api/v1/webhooks/whatsapp`). Es la primera superficie pública del ERP
  fuera del login.
- Nuevo adaptador `src/shared/integrations/whatsapp/`, reutilizable por
  cualquier módulo que necesite mensajería (candidatos: aviso de pedido
  listo, recordatorio de cobranza). No conoce a `marketing`.
