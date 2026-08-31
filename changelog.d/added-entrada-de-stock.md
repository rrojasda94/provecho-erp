- **Entrada de stock manual, con lote** (2026-08-30). `/inventario/ajustes`
  solo dibujaba Aprobar/Rechazar: el `POST /ajustes` que registra una entrada
  ya existía, pero no había ningún formulario que lo llamara. Ahora la
  pantalla ofrece "Registrar entrada de stock" (queda `pendiente`, la aprueba
  otro usuario — RN-INV-006) y, si el artículo controla lote, puede declarar
  código de lote y fecha de vencimiento al solicitarla. Antes esa fecha se
  perdía: el lote automático que crea `registrar_movimiento` cuando nadie
  pasa `lote_id` no la pide, y toda carga manual de un artículo con lote
  quedaba sin trazabilidad de vencimiento.
