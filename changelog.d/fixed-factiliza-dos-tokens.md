- **La consulta RUC/DNI tiene su propio token** (2026-08-22, ADR-005).
  Emisión y consulta son dos productos que Factiliza contrata y cobra por
  separado, y entrega una credencial para cada uno — pero el cliente mandaba
  `FACTILIZA_TOKEN` a los dos hosts. Con dos tokens distintos el buscador de
  DNI/RUC del mostrador recibía 401 de `api.factiliza.com` y moría con un 502
  genérico: el síntoma no nombra la causa, y el token de emisión seguía
  funcionando, así que la facturación se veía sana. Ahora
  `FACTILIZA_CONSULTA_DOCUMENTO_TOKEN` alimenta `consultar_dni`/`consultar_ruc`
  y `FACTILIZA_TOKEN` solo la emisión.
- **Vacío se reusa el de emisión**, así que quien tenga un plan con una sola
  credencial no configura nada nuevo. La cascada completa —argumento
  explícito, luego configuración, luego el de emisión— vive en
  `FactilizaClient._resolver_token_consulta`, no repartida por los métodos.
- **Se prueba el cruce en las dos direcciones.** Que la consulta use el suyo
  es la mitad fácil; la otra es que la emisión **nunca** use el de consulta,
  porque un comprobante firmado con la credencial equivocada lo rechaza SUNAT
  y eso sí llega a la caja. Los tests espían la cabecera `Authorization` de
  `httpx`, que es donde el error se vería.
- El token nuevo entra a `CLAVES_SENSIBLES` de `logging_config`, que redacta
  por nombre exacto: sin esa línea, la credencial recién agregada viajaba en
  claro a los logs y a GlitchTip.
