- `users` deja de decidir a quién le llega cada aviso y se queda con lo que
  siempre dijo ser: la bandeja. `destinatarios_de_sucursal` y
  `destinatarios_de_almacen` se mudaron tal cual a
  `reports/application/destinatarios.py`, donde pasan de ser *la* regla a ser
  dos resolutores dinámicos entre cuatro tipos de destinatario. Los cuatro
  handlers de `users/application/listeners.py` se reemplazan por uno solo, que
  consume `reports.reporte_emitido` con la lista ya resuelta. El usuario sigue
  teniendo **una sola campana**: `reports` publica un evento en vez de escribir
  en `notificacion`, que sigue siendo de `users`.
- `users.application.queries_publicas` expone `permisos_de(session,
  usuario_id)`: todos los códigos en una consulta, para **filtrar listas** por
  permiso (negar un acceso sigue siendo `require_permission`). Sin él, recortar
  un catálogo de 13 entradas costaba una consulta por entrada.
- Tres eventos ganan un campo, aditivo y compatible:
  `accounting.cierre_caja_irregular` += `sucursal_id`,
  `accounting.pago_requiere_aprobacion` += `empresa_id`,
  `production.no_conformidad_detectada` += `almacen_id`. Sin ellos el hecho no
  se puede atribuir a un tenant y su reporte no se puede escopar.
