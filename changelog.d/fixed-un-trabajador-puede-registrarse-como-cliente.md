- **No se podía dar de alta un cliente con solo su DNI** (2026-08-28). El
  botón "Guardar cliente" exigía teléfono aunque hubiera documento, y como
  estaba deshabilitado no pasaba nada al tocarlo: sin error, sin aviso, sin
  alta. El backend acepta cualquiera de los dos desde siempre. Le pasó a un
  trabajador que quiso registrarse para acumular puntos — ser trabajador nunca
  fue impedimento, el código lo contempla explícitamente.
- **Si esa persona ya era cliente, el PDV dejaba al cajero contra un 409**
  (2026-08-28). Pasa cada vez que alguien del local quiere consumir: su
  persona ya existe. Ahora se busca y se asigna al pedido, que es lo que se
  quería hacer.
- **Un cliente dado de alta solo con documento no se asignaba al pedido**
  (2026-08-28). La búsqueda posterior al alta usaba el teléfono en duro.
