- **El KDS mostraba siempre la primera sucursal del usuario** (2026-08-26). La
  pantalla de cocina resolvía su local con `usuario.sucursales[0]` y nada más:
  un jefe de cocina asignado a dos locales veía uno solo, y **no tenía ninguna
  forma de llegar al otro** —ni por URL—. El backend nunca tuvo el problema:
  `kds_pantalla.sucursal_id` existe desde el primer día y toda la cadena de
  estaciones se resuelve por sucursal. Ahora la sucursal viaja en la URL
  (`/kds?sucursal=<id>`), igual que la estación, así que la tablet se la lleva
  en su enlace de favoritos; lo que llega por ahí **se valida contra las
  sucursales del usuario** antes de pedir nada, porque la URL la escribe
  cualquiera. El selector solo aparece con más de una sucursal asignada.
- **Una estación se puede mudar de sucursal** (`PATCH /kds/pantallas/{id}` con
  `sucursal_id`). Una tablet que se lleva al local nuevo obligaba a recrear la
  estación allá y perder su configuración. Con dos guardas: **no se muda con
  pedidos en cola** —quedarían esperando en una cocina que ya no los mira,
  mismo criterio que borrarla— y **no se muda si el nombre ya existe en el
  destino**, que si no salía como un `IntegrityError` del índice único
  `(sucursal_id, nombre)` sin decirle a nadie qué hacer.
