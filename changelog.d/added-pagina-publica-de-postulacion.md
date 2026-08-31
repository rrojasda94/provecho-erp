- **El «enlace del formulario público» no era un formulario** (2026-08-30,
  ADR-087). Al publicar una convocatoria, la pantalla de contratación mostraba
  `/api/v1/rrhh/postulaciones/<token>` rotulado «Formulario público de
  postulación». Es una ruta **POST-only** de la API: quien la abría en el
  navegador —o la pegaba en el aviso, que es lo que el rótulo invita a hacer—
  recibía un 405. El único camino real era duplicar un Google Form y pegarle el
  token a mano en un Apps Script, por cada convocatoria. Ahora el ERP sirve su
  propia página, `/postular/{token}`: muestra puesto, vacantes, jornada y plazo,
  y la postulación cae en la columna «recibido» del tablero. El enlace se copia
  de la misma pantalla. **Google Forms sigue funcionando** por el mismo endpoint
  y con el mismo token —los scripts vivos no se tocan—, y conviene cuando la
  búsqueda necesita preguntas propias. Suma `GET /rrhh/postulaciones/{token}`
  (público, rate limit 60/h por IP) con cuatro campos y ninguno más: sin `id`,
  sin `empresa_id` y sin el rango salarial, que es dato de negociación y no del
  aviso. De paso, el `POST` deja de devolverle la ficha completa a un anónimo
  —le entregaba el id, la empresa, el estado interno del proceso y el plazo de
  conservación— y responde `{recibida, puesto}`: con un Apps Script que ignora
  la respuesta eso era inofensivo, con un navegador del otro lado no. Lo que la
  página **no** hace, y por qué: sin adjuntar CV (anonimizar todavía no borra el
  archivo, sería crear un problema de Ley 29733 en vez de resolver uno), sin
  preguntas configurables por convocatoria (para eso está Google Forms) y sin el
  texto del aviso, que vive en el canal por el que el candidato llegó.
