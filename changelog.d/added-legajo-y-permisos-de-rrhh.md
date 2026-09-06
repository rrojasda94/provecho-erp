- **RRHH tenía ocho familias de endpoints y una sola pantalla** (2026-09-05,
  Ola 3 de la auditoría del 2026-08-30). Contratos, sanciones, memorandos,
  certificados, permisos, pactos, boletas y liquidaciones estaban entregados,
  probados y con permisos sembrados, y el módulo mostraba la lista de
  trabajadores y nada más.
  - **Legajo del trabajador** (`/rrhh/trabajadores/[id]`): todo el expediente
    en una lectura. El endpoint ya devolvía las ocho listas juntas y nadie lo
    llamaba. Se entra desde el nombre en la lista, que antes no llevaba a
    ningún lado. La nómina se muestra solo con `rrhh.nomina_gestionar`, y
    cuando no, **se dice** — sin eso, un legajo sin sueldos se lee igual que
    uno censurado.
  - **Bandeja de permisos** (`/rrhh/permisos`): abre en las pendientes, porque
    quien entra ahí entra por «qué tengo que resolver». La consulta de la
    bandeja estaba escrita en el backend desde el slice del ciclo laboral.
    Aprobar y rechazar muestran su error debajo: la acción devuelve el motivo
    —solapamiento, trabajador cesado— y descartarlo dejaba la fila igual que
    si no hubiera pasado nada.
  - **Amonestación, memorándum y certificado de trabajo** se emiten desde el
    legajo. Quién firma sale de la sesión y no del formulario: dejarlo elegir
    sería poder firmar por otro, que es exactamente lo que un descargo va a
    discutir (RN-RRHH-002). El tiempo de servicios y el «dentro de plazo» del
    certificado los calcula el servidor: son la razón de ser del documento.
  - Costo aceptado: **registrar boletas y liquidaciones sigue siendo por API**.
    El ERP no liquida sueldos —registra lo que el contador liquidó— y el
    cuerpo lleva los conceptos como diccionario libre: eso pide una pantalla
    propia, no un diálogo. Queda anotado como deuda, igual que actas y socios.
- **`hoyEnZonaDelNegocio()`** en `lib/fechas.ts` (2026-09-05), con su prueba:
  `toISOString().slice(0, 10)` da el día **en UTC**, así que un formulario
  abierto a las 19:00 de Lima proponía la fecha de mañana.
