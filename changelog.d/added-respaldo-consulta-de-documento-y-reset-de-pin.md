- **Almacén abastecedor de respaldo** (2026-08-12, ADR-040, RN-INV-022,
  migración `a7c04e3b91d5`). Con un solo abastecedor, el día que ese almacén
  se da de baja la sucursal no puede pedir nada y recibe un "almacén
  abastecedor no encontrado" que no le dice a nadie qué hacer. Ahora
  `almacen` declara un respaldo y `crear_solicitud` cae a él **cuando el
  principal está dado de baja** — no cuando está sin stock, que tiene su
  propio camino. Un abastecedor pedido a mano nunca cae al respaldo:
  despachar desde donde no se pidió es lo que el que recibe no puede notar
  hasta contar la mercadería. La columna vive en `almacen` y no en
  `sucursal` (el que se abastece es el almacén, y una sucursal puede tener
  varios), pero se elige desde el formulario de Sucursal, que es donde se
  busca. Dar de baja un almacén ahora mira también a quien lo tenga de
  respaldo, y el respaldo viaja al hub: un corte de red es justo cuando no se
  puede ir a preguntar quién es el suplente.
- **Consulta de DNI y RUC desde la pantalla** (ADR-041). El cliente de
  Factiliza existía desde agosto, con pruebas, y **ninguna pantalla podía
  usarlo**: no había endpoint. `nombres_desde_dni` aplicaba el nombre de
  RENIEC al guardar (RN-PTS-004), así que quien tecleaba descubría recién
  después que el sistema había escrito otro. Ahora hay un botón "Buscar" en
  Personas (rellena nombres, apellidos y fecha de nacimiento) y en Proveedores
  (razón social, dirección y provincia), contra `GET /consulta/{dni,ruc}/{n}`
  en `core` — no tiene dueño de módulo: el mismo documento lo teclean
  personas, proveedores y caja. Prellena y no decide: todo queda editable, y
  si Factiliza no responde el alta sigue siendo posible tecleando. La
  respuesta **no** incluye el cuerpo crudo del proveedor, que trae más datos
  personales de los que la pantalla necesita (Ley 29733).
- **El proveedor guarda su domicilio fiscal** (`direccion`, `provincia`,
  `pais`), partido y no como un solo texto: `provincia` es lo que decide si
  el flete es local o interprovincial, y volver a partir una dirección
  concatenada es adivinar.
- **Reseteo de PIN con cambio obligatorio** (ADR-041). Un PIN olvidado no se
  recuperaba —está hasheado con Argon2id— y el frontend ni siquiera ofrecía
  cambiarlo: sus comentarios afirmaban que "lo cambia su dueño con su propia
  sesión", endpoint que no existía. Ahora `rrhh_admin` (permiso propio
  `users.resetear_pin`, aparte de `users.gestionar` en los dos sentidos)
  devuelve la cuenta al PIN por defecto, y pasan tres cosas juntas porque
  ninguna sirve sola: la cuenta **no puede hacer nada** salvo cambiarlo, se le
  revocan las sesiones abiertas, y se le limpia el lockout —quien olvidó su
  PIN normalmente lo agotó intentando—. La obligación la hace cumplir
  `get_current_user` leyendo la marca **de la base** y no de un claim, así que
  vale desde el request siguiente y no cuando venza el token; se verificó que
  ningún endpoint la esquiva. Suma `POST /users/me/pin`, que no lleva permiso
  —elegir la propia clave no es un privilegio que otorgar— pero exige el PIN
  actual.
- **`/users/me/pin` se declara antes que `/users/{usuario_id}/pin`**: FastAPI
  resuelve por orden de declaración y la ruta con parámetro capturaba `"me"`
  como si fuera un id, con lo que cambiar el PIN propio habría exigido
  `users.gestionar`.
