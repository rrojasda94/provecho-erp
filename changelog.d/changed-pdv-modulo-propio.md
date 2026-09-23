- **El PDV es un módulo propio del home** (2026-09-23, ADR-106). Antes se
  abría desde Ventas → "Abrir el PDV": el cajero, que no administra la
  jornada, tenía que pasar por el back-office cada vez que abría la caja.
  Ahora tiene su ficha en Operación, visible con el permiso exacto
  `sales.crear`; `/pdv` aplica el mismo gate con un mensaje que dice qué
  permiso pedir. Ventas queda como back-office (jornada, clientes, mesas,
  promociones). El backend no cambió.
