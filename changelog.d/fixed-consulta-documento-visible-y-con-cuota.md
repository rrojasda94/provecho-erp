- **La búsqueda por DNI/RUC no estaba donde se necesitaba** (2026-08-15,
  ADR-041). El botón existía y se montaba en Personas y en Proveedores, pero
  no en **Ventas → Clientes**, que es la pantalla donde se corrige la razón
  social de un cliente jurídico — y cuyo propio texto de ayuda ya decía que
  "SUNAT manda sobre la razón social tecleada". Ahora está ahí, prellenando
  solo la razón social: `contacto` es el teléfono o el correo de quien
  coordina, y traerle el domicilio fiscal reemplazaría un dato real por otro.
  **No** se montó en el diálogo de documento de un cliente natural: ese
  formulario no tiene ningún campo que la consulta pueda llenar (el nombre
  vive en su `persona`, RN-GEN-007, y ahí el botón ya estaba).
- **El botón se le ofrecía a quien no puede usarlo** (2026-08-15). Ningún
  punto de montaje miraba `consulta.documento`: un `contador` o un
  `almacenero` lo veía, lo apretaba y se comía un 403 dibujado como aviso.
  El gate vive ahora **dentro** de `BuscarDocumento` —repetirlo en cada
  pantalla es cómo la siguiente se lo olvida— y `permisos` es una prop
  obligatoria, así que montarlo sin decir de quién es la sesión no compila.
  Sigue siendo UX: quien manda es `require_permission` en la API.
- **La consulta de DNI/RUC ya tiene cuota propia** (2026-08-15), deuda
  declarada con ADR-041. Cada llamada gasta crédito de un proveedor **pago**,
  así que lo que se cuida no es el abuso sino el gasto: un bucle mal escrito
  en una pantalla agota el plan del mes sin que nadie ataque nada. Se reusó
  `core/rate_limit.py` en vez de escribir otro limitador —fail-open incluido:
  un Redis caído no puede dejar a la caja sin identificar a un cliente—.
  **Por usuario además de por IP** (20 y 60 por minuto, configurables): en un
  local todas las cajas salen por la misma dirección, y un límite solo por IP
  deja al equipo entero sin consultar por culpa de uno. Se cuenta después del
  permiso, porque un 403 no le cuesta un centavo a nadie.
