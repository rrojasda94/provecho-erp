- **La sesión sobrevivía a apagar la PC** (2026-08-30, ADR-084). Las dos
  cookies se plantaban con `Max-Age` —15 minutos y 7 días—, y una cookie con
  `Max-Age` es persistente: el navegador la escribe en disco y no la borra al
  cerrarse. Al volver, el middleware rotaba el refresh y replantaba las dos con
  el plazo completo, así que la sesión era una ventana deslizante de siete días
  que ningún gesto del usuario cerraba. Del lado de la API tampoco había corte:
  cada rotación emite una fila nueva con vencimiento a siete días, de modo que
  usar la sesión la renovaba para siempre. Ahora **las cookies son de sesión**
  (mueren al cerrar el navegador) **y** `auth.refresh` corta a las 8 horas de
  inactividad, revocando la cadena entera. Hacían falta las dos: «restaurar
  pestañas» devuelve las cookies de sesión intactas tras un apagón, y el corte
  del servidor solo no evitaría dejar el refresh en el disco de un equipo
  compartido. El plazo sale de `REFRESH_INACTIVIDAD_HORAS` (8 h: entra un turno
  completo, no entra una noche; `0` lo apaga) y se mide contra el `created_at`
  del token — no hace falta columna nueva porque la rotación ya inserta una
  fila por renovación. Costo aceptado y escrito en el ADR: la tablet del pad de
  asistencia pide login a la mañana siguiente; su enrolamiento (un año,
  ADR-079) no se pierde.
