- **Una cuenta impaga se leía como «Ese DNI no figura»** (2026-08-26). El
  producto de consulta de Factiliza devuelve **405** con
  `{"success": false, "message": "Token con falta de pago…", "plan": 0}`
  cuando el plan no está al día. Ese código no era 404, ni 401/403, ni ≥ 500
  —los tres únicos que `_consultar` sabía nombrar—, así que el cuerpo se
  parseaba como si fuera bueno, `success: false` salía como
  `encontrado: false`, y el cajero leía **«Ese DNI no figura. Completa los
  datos a mano.»** para todos los documentos del mundo. Un problema de
  facturación disfrazado de RENIEC vacío es un problema que nadie va a ir a
  buscar donde está. Ahora la regla es la general y no una lista: **cualquier
  estado ≥ 400 que no sea el 404-vacío es fallo del proveedor**, y se nombra
  con el `message` que él mismo manda. Un `success: false` con 200 tampoco
  pasa por resultado. El alta sigue siendo posible tecleando, como siempre —lo
  que cambia es que ahora se puede saber por qué.
- **El motivo del fallo va al log, no a la pantalla de caja.** El 502
  concatenaba `str(e)` en el `detail`, así que al cajero le llegaban nombres de
  variables de entorno y el WhatsApp de soporte del proveedor. Ahora lee «No se
  pudo consultar el documento. Completa los datos a mano.» y el detalle
  completo queda en el log del servidor, que es donde lo busca quien puede
  hacer algo con él.
- **Timeout propio para la consulta: 8 s en vez de 30.** Compartía número con
  la emisión, que corre en cola y puede tardar lo que SUNAT tarde. La consulta
  la espera una persona con el botón deshabilitado y un cliente en el
  mostrador: medio minuto ahí no es lentitud, es un cuelgue. Nuevo
  `FACTILIZA_CONSULTA_TIMEOUT_SEGUNDOS`.
