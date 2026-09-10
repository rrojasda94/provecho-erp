- **Una cocina de producción podía despachar directo a una sucursal** (2026-09-09,
  bloque `fix/inventario-cdp-001-y-conteo-produccion` del plan de deuda de
  producción). RN-CDP-001 dice que una cocina de producción solo entrega al
  almacén central, nunca directo a un local — la regla estaba en tres
  documentos y en ningún código: `inventory.application.transferencias.
  _validar_almacenes` no distinguía ningún `tipo` de almacén. Ahora un
  despacho de un almacén `produccion` a uno `sucursal` responde 409; el mismo
  origen sigue pudiendo despachar al central, que es el tramo real.
- **El conteo cíclico del almacén de producción no tenía ni una prueba**
  (mismo bloque). El caso de uso siempre fue genérico por `almacen_id` — nunca
  miró `almacen.tipo` — así que no había nada que arreglar, solo que probar:
  `test_conteo_ciclico_funciona_igual_en_almacen_de_produccion` abre, cuenta
  y cierra un conteo sobre un almacén `produccion` con el mismo resultado
  (ajuste por diferencia) que sobre el central, cerrando RN-PRD-016.
