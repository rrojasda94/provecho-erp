- **El rastro de cambios se puede leer** (2026-09-05, Ola 3 de la auditoría
  del 2026-08-30). `GET /api/v1/auditoria` existía con sus filtros y su
  alcance por tenant, y **no lo llamaba ninguna pantalla**: el `audit_log`
  que el ERP viene escribiendo desde ADR-031 —quién tocó qué, cuándo, con qué
  valor anterior— solo se podía leer con una consulta a la base. Auditar era
  pedirle a alguien que contara qué hizo.
  Módulo propio (`/auditoria`) y no una sección de Gerencia, por el mismo
  criterio que Organización: el permiso real es `auditoria.leer` y colgarlo de
  otro prefijo se lo escondería justo a quien sí lo tiene — hoy el contador,
  que audita a Compras, Almacén y las cajas de sucursal (RN-CTB-009).
  La columna «cambio» muestra **solo lo que cambió**: volcar los dos
  diccionarios enteros es ilegible, en una fila de doce campos once son
  iguales y el que importa se pierde. Un cambio sin usuario se lee «el
  sistema» —un barrido programado, un listener— y no como un dato faltante.
  Costo aceptado: los nombres de usuario se piden aparte y con `catch`,
  porque un contador tiene `auditoria.leer` y no `users.gestionar`; sin ellos
  la pantalla muestra el id y sigue sirviendo.
