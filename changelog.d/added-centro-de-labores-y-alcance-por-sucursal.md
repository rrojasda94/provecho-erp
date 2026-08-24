- **Ya se puede decir dónde trabaja alguien y qué locales alcanza su cuenta**
  (2026-08-24, ADR-061, migración `b6d29f10c47e`). Eran dos huecos que desde
  la pantalla se veían como uno: `trabajador` no tenía sucursal —la asistencia
  no tenía a qué local atribuirse y el reemplazo entre sucursales
  (RN-RRHH-011) no era representable— y `usuario_sucursal` tenía endpoints
  desde el slice inicial **pero ninguna pantalla**, así que fuera del seeder
  nadie repartía alcance. Ahora `trabajador.sucursal_id` (nullable) es el
  centro de labores, un hecho laboral que vive en RRHH → Trabajadores, y el
  alcance de datos se reparte en Usuarios → Cuentas con la misma celda de
  chips que ya se usaba para los roles. Un supervisor a cargo de varios
  locales son **varias filas** de `usuario_sucursal`: se descartó una tabla
  `zona` porque hoy ningún reporte, permiso ni regla la nombra — sería una
  entidad con su tenant, su seeder y su CRUD para ahorrar dos clics. El costo
  aceptado: el alcance viaja en el token, así que un cambio le aplica a esa
  cuenta recién cuando su sesión renueve; la pantalla lo advierte en vez de
  invalidar tokens vivos.
- **`GET /users/{id}/sucursales`**: el alcance de una cuenta ajena no se podía
  leer. `/users/me` devolvía el propio, que no sirve para administrar a otro.
