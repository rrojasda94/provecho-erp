- **Una receta que ya existe se actualiza en vez de omitirse** (2026-08-20,
  ADR-051, RN-COM-031). Desde ADR-046 el nombre repetido se informaba y la fila
  no entraba, y la deuda quedó abierta a propósito: actualizar exigía decidir
  qué pasa con los ingredientes que el archivo no menciona, y eso es decisión de
  negocio, no de código. La decisión: **se conservan**, y la revisión deja
  pedir que se quiten **receta por receta**, mostrando antes cuántas líneas se
  pierden. El defecto no borra porque el modo de falla es asimétrico — subir la
  hoja equivocada no puede vaciar una receta sin que nadie vea el número.
- **La identidad de una fila es la columna `ID`, no el nombre.** Sin ella,
  renombrar y duplicar son indistinguibles: el nombre es justamente lo que
  alguien quiere cambiar. La regla que gobierna a las tres entidades es que *la
  clave de actualización tiene que ser un campo que la persona no está
  editando* — de ahí que artículos acepten además su **código interno** y
  clientes su **número de documento**, y que recetas solo acepten `ID`.
- Un `ID` repetido dentro del mismo archivo marca **las dos filas**, no la
  segunda: copiar-pegar una fila entera es el accidente esperable, y silenciarlo
  escribiría dos veces sobre el mismo registro.
- Una fila con `ID` que no resuelve **no se degrada a alta**. Se informa y se
  omite con motivo: un id mal pegado convertido en registro nuevo es un
  duplicado que nadie sale a buscar.
- La respuesta de importar pasa de `{creadas, omitidas}` a
  `{creadas, actualizadas, omitidas}` en las tres entidades.
- **La cantidad se exporta como la expresión tecleada, no como el resultado.**
  Una línea escrita `450/3` vuelve a bajar `450/3`, no `150`: el dominio guarda
  las dos y exportar solo el número perdería justo lo que RN-COM-024 existe para
  conservar.
