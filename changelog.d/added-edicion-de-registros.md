- **Los registros maestros por fin se editan desde la pantalla** (2026-08-10).
  Hasta ahora el ERP sabía crear y listar, no corregir: un RUC mal tecleado, un
  cargo que cambió o un código de estante equivocado solo se arreglaban con
  `curl` o tocando la base. El diagnóstico no era el esperado — el backend ya
  tenía `PATCH` para casi todo; lo que faltaba era la pantalla.
  - **Botón "Editar" en la fila** de Proveedores, Artículos, Trabajadores,
    Cuentas de usuario, Plan de cuentas y Divisas. Cada diálogo dice también
    **qué no se puede cambiar y por qué**: la unidad de medida de un artículo
    (el stock y las recetas ya están expresados en ella, cambiarla no convierte
    nada, reinterpreta en silencio lo que ya existe), el `username` de una
    cuenta (firma cada línea del `audit_log`), el código y el tipo de una
    cuenta contable (los asientos registrados dependen de ellos), el tipo de un
    proveedor (dejaría sus órdenes de compra apuntando a algo que ya no es).
  - **Ocho pantallas nuevas**: Usuarios → Personas, Ventas → Clientes,
    Inventario → Categorías y Unidades de medida, y el módulo **Organización**
    completo (empresas, marcas, sucursales, almacenes). Ninguna existía: esos
    registros solo se administraban por API.
  - **Personas lleva bloqueo optimista** y es la única que lo necesita: la
    `version` viaja con el formulario y un 409 se muestra con instrucción de
    recargar. Sin eso, dos administradores editando la misma ficha se pisaban
    en silencio — sobre datos personales eso significa "el domicilio corregido
    volvió al viejo y nadie se enteró". Con esta pantalla el derecho de
    **rectificación** de la Ley 29733 deja de ejercerse por `curl`.
  - **De un cliente natural solo se completa el documento**: su nombre,
    teléfono y dirección viven en su `persona` (RN-GEN-007) y el diálogo
    enlaza allá. Ofrecer esos campos en la pantalla de clientes habría creado
    justo la segunda fuente que esa regla existe para evitar.
  - Tres huecos de API cerrados: `ProveedorUpdate` admite razón social y RUC,
    `ArticuloUpdate` admite `id_interno`, y `sales` gana
    `PATCH /clientes/{id}` más `GET /clientes/listado` paginado.
  - **Costo aceptado**: desde un `PATCH` sigue sin poderse *vaciar* un campo
    opcional (`null` significa "no tocar"). Solo `frecuencia_conteo` tiene su
    centinela; el resto se cambia por otro valor, no se borra.

- **Un formulario del ERP no se administraba solo** (2026-08-10). El shell del
  `<dialog>` estaba copiado y pegado en siete pantallas; con la edición encima
  habrían sido veinte copias del mismo bloque, y la que se olvidara de cerrar
  al `ok` iba a ser un bug sin relación aparente con las otras diecinueve. Vive
  en `components/formulario/dialogo-formulario.tsx` y lo usan tanto las altas
  como las correcciones.

- **Un rechazo del servidor ya no borra lo tecleado** (2026-08-10). React 19
  **resetea solo** el formulario cuando la acción va en el prop `action` de
  `<form>`, y lo hace también cuando la acción devolvió error. Encontrado
  verificando en el navegador: corregir un RUC y errarle al plazo de crédito
  dejaba el diálogo abierto con el RUC viejo de vuelta. Ahora la acción se
  despacha a mano dentro de una transición — sin reset automático y con
  `pendiente` funcionando igual. Es el mismo candado que el conteo de caja ya
  tenía probado en e2e: reteclear un formulario entero porque un campo estaba
  mal es la fricción que termina en un dato inventado.
