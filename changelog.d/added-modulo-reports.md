- Módulo `reports`: emisión y distribución de reportes (ADR-033). El ERP
  publicaba 52 eventos y solo **cuatro** llegaban a una persona, cableados en
  `users/application/listeners.py`; a quién le llegaban lo decidían dos
  funciones fijas cuyo propio docstring declaraba el hueco («el punto de
  configuración futuro está en `destinatarios_de_sucursal`»). No había forma
  de ver el mapa ni de cambiarlo sin un deploy, y varias reglas de negocio que
  exigen reportes dirigidos (RN-CTP-004, RN-INV-020, RN-INV-021, RN-PRD-009)
  seguían sin implementar — `inventory.conteo_vencido` ya publicaba
  `dirigido_a: ["almacen","gerencia"]` y no había nadie del otro lado. Ahora
  hay áreas, reglas por (empresa, emisión, sucursal) y una **matriz** que
  además marca lo que falta: **huecos** (el hecho ocurre y no se entera nadie)
  y **fugas** (regla activa que no llega a nadie). Trece emisiones cableadas,
  incluidas las cuatro migradas. Migración `9a1c4e7b2d30`.
- El catálogo de emisiones es **cerrado y en código**, no una tabla: la regla
  configura *a quién* llega un reporte, nunca *qué datos* lee. Si fuera
  administrable por API, quien puede crear reglas podría hacerse enviar
  cualquier payload del bus. Costo aceptado: una emisión nueva es un cambio de
  código, no de configuración.
- Leer un reporte exige **dos** puertas: ser destinatario y tener el permiso
  del módulo dueño del hecho. Estar en la lista de distribución no da acceso
  al dato — un cocinero puede enterarse de que hubo un descuadre de caja sin
  ver el detalle de la caja. `reports.leer_matriz` es un permiso aparte
  porque el mapa revela la estructura organizacional; `reports.administrar`
  queda solo en `admin`.
- Las entregas **no son retroactivas**: `regla_id` y el motivo de cada entrega
  (`area:almacen`, `dinamico:encargado_de_turno`) se congelan al emitir, así
  que cambiar la distribución mañana no reescribe a quién le llegó ayer. Todo
  cambio de área o regla queda en `audit_log`, que es la respuesta a «¿alguien
  tocó los flujos?» sin mantener un historial en paralelo.
- Una emisión sin destinatarios ahora **se guarda igual**, con cero entregas.
  Antes era un `log.warning` que nadie leía; un aviso que no llegó a nadie es
  información de gestión, no un no-evento.
