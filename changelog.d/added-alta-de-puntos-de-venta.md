- **Los puntos de venta se dan de alta desde la app** (ADR-059). La caja de
  una sucursal —lo que carga las series SUNAT con las que el local emite—
  solo existía en el seeder: en staging el PDV bloqueaba con "La sucursal no
  tiene puntos de venta" y el mensaje pedía configurar una caja sin decir
  dónde, porque no había dónde. Ahora hay pantalla en **Organización →
  Puntos de venta**, entre Sucursales y Almacenes, con `POST` y
  `PATCH /api/v1/sales/puntos-venta`.
- El alta la firma `organizacion.gestionar` y no un permiso de `sales`:
  asignar una serie SUNAT es identidad fiscal de la empresa, del mismo orden
  que fundar el local, no configurar el salón. El listado acepta cualquiera
  de los dos permisos — el cajero necesita leerlo para abrir el PDV y el
  administrador que da de alta las cajas puede no tener ninguno de venta.
- `GET /api/v1/sales/puntos-venta` ya no exige `sucursal_id`: sin él devuelve
  las cajas de la empresa. Antes, un administrador sin sucursal asignada no
  podía listarlas.
- Se validan las reglas que el seeder daba por buenas porque las tipeaba a
  mano: la **serie no se repite dentro de la empresa** (RN-CPP-007, el
  correlativo es único por empresa y serie), las cuatro series de una caja
  son distintas entre sí (RN-CPP-009), web y kiosko cobran por adelantado
  (RN-POS-005), y un punto de venta web no lleva equipo asociado. La
  unicidad de serie vive en el caso de uso y no en el esquema: `punto_venta`
  no tiene `empresa_id` y el candado que de verdad impide emitir un duplicado
  ya existe en `comprobante`.
- Corregir una serie no reescribe lo ya emitido: cada comprobante guarda la
  suya al emitirse. Lo que no se permite es mudar una caja de sucursal.
- `PuntoVentaOut` expone `serie_nc_boleta`, `serie_nc_factura` y
  `hardware_id`, que existían y no se veían. Sin las primeras no se podía
  saber si una caja puede acreditar lo que emitió.
