- `core/sync/serializacion.marca_de` devolvía marcas *naive* mientras el resto
  del motor de sync trabaja en UTC *aware*, así que el pull de un recurso con
  más de una página reventaba con `TypeError: can't compare offset-naive and
  offset-aware datetimes`. El bug estaba desde que existe la paginación y
  nunca se había visto porque ningún recurso sembrado pasaba de 100 filas:
  apareció al sumar los permisos de `reports` (`rol_permiso` pasó de 97 a
  109). Se normaliza en `marca_de`, que es el único borde donde un texto
  entrante se vuelve `datetime`, así que cubre a todo el motor de una vez.
