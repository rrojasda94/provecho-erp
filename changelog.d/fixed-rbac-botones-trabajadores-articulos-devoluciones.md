- **Los últimos botones que prometían 403** (2026-09-04, auditoría del
  2026-08-30 §3). Tres pantallas ofrecían acciones a cualquiera que pudiera
  *ver* la lista, y las tres páginas ya llamaban a `obtenerSesion()` — solo
  tiraban el `usuario` y se quedaban con el token:
  - **Trabajadores**: «+ Nuevo trabajador», «Editar» y «Cesar» exigen
    `rrhh.trabajador_gestionar`.
  - **Artículos**: «+ Nuevo artículo», «Editar» y el importador de Excel
    exigen `inventory.gestionar_catalogo`. «Exportar» no se toca: bajar el
    catálogo que ya se está viendo no pide más permiso que verlo.
  - **Devoluciones**: «+ Nueva devolución» y «Anular» exigen
    `inventory.registrar_movimiento` — las dos mueven stock real.

  Con esto queda cerrado el hallazgo §3 completo. Eran **cinco** pantallas y
  no seis: la ficha de orden de compra ya estaba gateada desde ADR-085 y la
  auditoría la contó de más.

  Verificado en el navegador con tres roles del seeder: `almacenero` ve
  Artículos sin ningún control de alta y solo con «Exportar», pero sí puede
  registrar una devolución; `supervisor` es el inverso —gestiona catálogo, no
  registra devoluciones—; `admin` sigue viendo todo. La autorización real es
  la de la API, como siempre: el gate es UX, para que un botón no termine
  siempre en 403.
