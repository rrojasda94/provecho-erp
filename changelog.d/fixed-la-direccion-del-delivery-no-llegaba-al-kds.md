- **La dirección del delivery nunca llegaba a la pantalla de despacho.**
  `cola_pantalla` (`src/modules/sales/application/kds.py`) la emitía en el
  dict de cada pedido —con un comentario explícito de que despacho arma la
  bolsa mirando esa pantalla—, pero `PedidoColaOut`
  (`src/modules/sales/api/kds_schemas.py`) no declaraba el campo, así que
  pydantic lo descartaba al serializar `GET /kds/pantallas/{id}/cola` y el
  navegador nunca lo veía. Mismo fallo que `ItemColaOut.valores` (ADR-067):
  dato emitido y schema que no lo declara. `PedidoColaOut` gana
  `direccion_entrega: str | None`, el tipo `PedidoCola` de
  `frontend/lib/kds.ts` lo espeja y la tarjeta de despacho
  (`frontend/app/kds/despacho-cliente.tsx`) lo muestra solo cuando la
  modalidad es `delivery`. Cubierto por
  `test_despacho_ve_la_direccion_del_delivery` en `tests/test_kds.py`, y el
  contrato en `docs/architecture/openapi.json` quedó regenerado.
