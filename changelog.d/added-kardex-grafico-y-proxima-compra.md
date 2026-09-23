- **Kardex gráfico en la ficha del artículo** (2026-09-23, ADR-108). Desde
  Inventario (nombre en la lista de artículos) o desde Compras (cada línea de
  una OC) se ve: el precio de cada compra recibida, las entradas y salidas
  por semana, el saldo contra el stock mínimo, cada cuántos días se compra y
  la **próxima compra sugerida**, el día en que el stock toca el mínimo al
  ritmo de consumo de los últimos 90 días (RN-INV-027). Dos endpoints nuevos:
  `GET /inventory/articulos/{id}/kardex` y
  `GET /purchases/articulos/{id}/historial-precios`. La sugerencia todavía no
  resta el plazo del proveedor (deuda anotada).
