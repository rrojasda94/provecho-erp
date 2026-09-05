- **La sesión se moría y la pantalla no se enteraba** (2026-09-04, auditoría
  del 2026-08-30 §10, ADR-088). Desde ADR-073 el token se renueva solo, así
  que un 401 que igual llega al navegador significa que el refresh está
  vencido, revocado o reusado — la señal más confiable de «volvé a entrar»
  que tiene el cliente. No la escuchaba nadie:
  - el **KDS** lo mostraba cuatro segundos y seguía refrescando cada tres, con
    la cola de cocina congelada en el último dato bueno;
  - la **campana** lo tragaba entero (`catch {}`) y mostraba el conteo viejo,
    y al marcar una notificación como leída la sacaba de la lista para
    siempre;
  - los **borradores del PDV** lo tragaban también **y borraban su huella de
    guardado**, así que cada tecla reintentaba un PUT que fallaba. El cajero
    no veía nada y se enteraba al recargar, con las pestañas vacías: pérdida
    de datos en silencio.

  Ahora el 401 se detecta en un solo lugar —`lib/cliente-api.ts`, por donde
  salen todas las llamadas del navegador—, se anuncia **una vez** con un
  diálogo modal montado en el layout raíz (que es el único ancestro común de
  `(app)`, `/pdv` y `/kds`) y **corta en seco** las llamadas siguientes sin
  salir a la red, que es lo que apaga el bucle del KDS y el PUT por tecla del
  PDV.

  Costo aceptado: el aviso dice que la sesión murió, no rescata el formulario
  a medio llenar. Guardar eso antes de reintentar es otro alcance.
- **La suite de sesión probaba solo la mitad del caso** (2026-09-04). El test
  existente borra la cookie de acceso, que es justo el caso que ADR-073 sí
  salva. El nuevo borra **las dos** y espera el aviso en el KDS, que es la
  única pantalla que pregunta sola y seguido.
