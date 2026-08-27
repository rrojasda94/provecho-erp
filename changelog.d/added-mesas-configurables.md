- **Las mesas del salón ya se pueden configurar, con plano** (2026-08-27,
  ADR-069). `mesa` existía desde ADR-018 pero solo el seeder de demo podía
  darla de alta: no había `PATCH`, la única "baja" no miraba si tenía
  historia, y una sucursal nueva quedaba con el PDV diciendo "esta sucursal
  no tiene mesas configuradas todavía" sin ninguna salida. Nueva pantalla
  `/ventas/mesas`: el número lo asigna el sistema (1..n sin huecos, no
  editable), solo se retira la mesa de número más alto, ni editar ni retirar
  proceden con una orden abierta, y cada mesa se ubica arrastrándola en un
  plano de 12 columnas — mismo plano que ahora pinta el mapa del PDV. Suma al
  tablero de reportes qué mesa prefiere la gente por sucursal
  (`mesas_preferidas`). De paso cierra un hueco de tenant: la ruta que
  desactivaba una mesa era la única de las cuatro sin validar la sucursal del
  usuario contra la del recurso.
