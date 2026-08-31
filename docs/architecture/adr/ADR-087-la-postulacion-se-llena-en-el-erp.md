# ADR-087 — La postulación se llena en el ERP; Google Forms queda como camino alterno

- Estado: aceptado
- Fecha: 2026-08-30
- Contexto: módulo `rrhh` (convocatoria y postulante), grupo de rutas
  `frontend/app/(publico)`
- Relacionado: ADR-061 (el cupón de la landing vive en `sales` — el primer
  formulario público del ERP), ADR-080 (la landing tiene dominio propio),
  ADR-011 (la cancelación es anonimización), RN-PER-004 (consentimiento),
  RN-RRHH-013 (sin perfil no se publica),
  `docs/roadmap/auditoria-erp-2026-08-30.md` (hallazgo #5)

## Contexto

El slice de contratación (2026-08-01) decidió que el formulario del candidato
fuera **Google Forms + un Apps Script de 12 líneas**, y no una página propia:
en ese momento el ERP no tenía ninguna superficie pública, hospedar un
formulario significaba resolver CSP, dominio y estilo de cero, y Google Forms
era gratis y conocido por el candidato.

Lo que quedó fue un hueco silencioso. Al publicar una convocatoria, la
pantalla de contratación mostraba `/api/v1/rrhh/postulaciones/<token>`
rotulado **«Formulario público de postulación»**. Eso no es un formulario: es
una ruta POST-only de la API. Quien la abría en el navegador —o la pegaba en
un aviso de Facebook, que es exactamente lo que el rótulo invita a hacer—
recibía un 405. El único camino real exigía duplicar un Google Form y pegar el
token en su Apps Script, por cada convocatoria, a mano. La auditoría
backend↔frontend del 2026-08-30 lo listó como hallazgo #5, severidad alta.

Entre medio cambió el costo de la alternativa: `(publico)` existe desde
ADR-061, con su layout de marca, su CSP con nonce resuelta y el patrón de
Server Action **sin token de sesión** ya probado en producción. Una segunda
página pública dejó de ser infraestructura nueva para ser una carpeta más.

## Decisión

**El ERP sirve su propia página de postulación en `/postular/{token}`, y
Google Forms deja de ser el único camino sin dejar de funcionar.**

### 1. Un `GET` público sobre la misma ruta que ya recibía el `POST`

`GET /api/v1/rrhh/postulaciones/{token}` devuelve lo que la página necesita
para dibujarse: `puesto`, `vacantes`, `jornada_horas_semana` y
`fecha_limite`. Sin JWT y sin tenant, igual que el `POST`: el token es toda la
autorización que hay, y por eso solo existe mientras la convocatoria está
publicada.

No se creó `rrhh/api/publico_routers.py` como en `sales`: acá son **dos rutas
sobre el mismo path**, y separarlas en archivos distintos haría más difícil
ver que comparten token, guardas y límite. La regla de «cuándo una
convocatoria sigue abierta» sí se extrajo a
`convocatorias.publicada_por_token`, porque ahora la usan los dos lados.

### 2. Se lee lo mínimo, y el acuse también

El `GET` **no** expone `id`, `empresa_id`, `estado` ni el rango salarial. El
rango es dato de negociación, no del aviso — y es justo lo que otra rama de la
misma auditoría está cerrando del lado autenticado.

El `POST` deja de devolver `PostulanteOut` y responde
`{recibida, puesto}`. Antes le entregaba a un anónimo el `id` de la ficha, el
`empresa_id`, el estado interno del proceso y el plazo de conservación. Con un
Apps Script que ignora la respuesta eso era inofensivo; con un navegador del
otro lado, no. El id que el proceso necesita sale del tablero, que exige
`rrhh.leer`.

Cerrada, vencida y token inventado se muestran igual al candidato. Distinguir
los casos solo le confirmaría a un curioso que ese token existió.

### 3. La URL que se pega en el aviso es la de la página, no la de la API

`enlaceDe` en la pantalla de contratación devuelve `/postular/{token}` y se
pinta como enlace abrible con botón de copiar. El token sigue a la vista al
final de la URL: quien ya tiene su Google Form armado lo copia de ahí, como
antes.

### 4. Lo que la página NO hace

- **No adjunta CV.** `postulante.cv_archivo_id` existe, pero anonimizar hoy no
  borra el archivo (deuda abierta en
  `docs/roadmap/deuda/proteccion-de-datos-personales.md`). Aceptar archivos
  antes de poder borrarlos sería crear un problema de Ley 29733, no resolver
  uno.
- **No tiene preguntas configurables por convocatoria.** Hay una sola pregunta
  abierta, que viaja dentro de `respuestas`. Modelar un cuestionario por
  convocatoria es una entidad nueva y una pantalla de armado; quien de verdad
  la necesite tiene Google Forms, que sigue entrando por el mismo endpoint.
- **No muestra el aviso.** `convocatoria` no tiene campo de texto del aviso: la
  página enseña puesto, vacantes, jornada y plazo. El aviso —funciones,
  sueldo, requisitos— ya lo leyó el candidato en el canal por el que llegó.

## Consecuencias

- Publicar una convocatoria entrega un enlace pegable el mismo minuto, sin
  duplicar un formulario ni tocar un script.
- Google Forms sigue siendo válido y los Apps Script vivos no se tocan: mismo
  token, misma URL, mismo cuerpo. Solo cambió el cuerpo de la **respuesta**,
  que ese script no lee.
- Aparece la segunda superficie del ERP abierta a internet en `rrhh`. Se cubre
  con lo mismo que la primera: rate limit por IP (60/h para leer, los 20/h que
  ya existían para escribir), campos acotados en el schema y consentimiento
  obligatorio con finalidad y plazo a la vista.
- Las primitivas de formulario de `(publico)` se renombraron de
  `reconocerte-*` a `publico-*`: eran genéricas y ahora las usan dos páginas.
