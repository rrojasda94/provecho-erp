- **La cola de pagos a proveedor ofrecía dos botones que terminaban en 403**
  (2026-09-04, auditoría del 2026-08-30 §3). «Ejecutar» y «Rechazar» se
  dibujaban para cualquiera que pudiera *ver* la cola; la API exige
  `accounting.pago_gestionar`. Ahora el permiso decide si la acción se
  ofrece, con el mismo criterio que la jornada de ventas: la autorización
  real sigue siendo la de la API, pero un botón que siempre falla es peor que
  no tenerlo. **`accounting.pago_aprobar` no gatea el botón** a propósito —no
  gatea la ruta tampoco: decide si un pago *sobre el umbral* sale derecho o
  queda esperando firma, así que esconder por él le sacaría la cola al
  contador, que paga todos los días por debajo del umbral.
- **Errarle a un dato del pago borraba el formulario entero** (2026-09-04,
  auditoría §4). El diálogo de ejecución pasa a `DialogoFormulario`, que
  despacha la acción a mano en vez de por el prop `action` del `<form>`:
  React 19 resetea los campos no controlados cuando la acción termina,
  también cuando devolvió error. Costo aceptado: el diálogo cambia de aspecto
  (pasa a los tokens del sistema, con encabezado y pie fijos) — que es el
  punto de tener un solo molde.
- **Rechazar un pago no decía si había fallado** (2026-09-04, auditoría §11).
  `rechazarPagoAction` devolvía su error y la pantalla lo descartaba con
  `void`: un rechazo que fallaba se veía idéntico a uno que salió —la fila
  seguía ahí y nadie sabía por qué. El error se muestra bajo el botón, igual
  que en «Anular» de la jornada.
- **El roadmap de la auditoría del 2026-08-30 entra al repositorio**
  (2026-09-04). Vivía sin versionar en un worktree suelto y ADR-087 ya lo
  citaba como enlace roto: un `git clean` lo borraba para siempre.
