# ADR-090 — La consulta de documento se cachea, con TTL

- Estado: aceptado
- Fecha: 2026-09-06
- Contexto: `src/shared/integrations/factiliza/cache.py`,
  `src/shared/integrations/factiliza/client.py`
- Relacionado: ADR-005 (Factiliza), ADR-041 (reseteo de PIN y consulta de
  documento), ADR-054 (la tarifa del delivery se cobra por kilómetro —
  `_distancia_cacheada`)

## Contexto

`consultar_dni`/`consultar_ruc` se pagan por llamada a Factiliza, y hoy se
llaman **dos veces** por cada alta: el botón «Buscar» del formulario
consulta una vez para prellenar, y al guardar
`nombres_desde_dni`/`razon_social_desde_ruc` vuelven a consultar el mismo
documento desde el servidor — deliberado, ADR-041, para no confiar en lo
que llegó del cliente. Son dos llamadas a un proveedor pago por cada
persona que se da de alta, y con el proveedor caído, dos timeouts seguidos
en vez de uno.

## Decisión

**Se cachea la respuesta de negocio (`ConsultaPersona`/`ConsultaEmpresa` ya
interpretadas), no el transporte.** Un fallo del proveedor
(`FactilizaError`) nunca llega a `cache.guardar` —la excepción sale antes—,
así que el siguiente intento vuelve a salir a la red en vez de repetir el
mismo error durante todo el TTL.

**Con TTL, y por eso no se copia `sales.tarifa_delivery._distancia_cacheada`**
(`lru_cache` sin vencer, en memoria del proceso). La distancia entre dos
puntos fijos no cambia nunca; un documento sí —cambio de nombre, RUC dado
de baja— así que guardarlo para siempre mostraría un dato viejo sin
límite. 5 minutos alcanza para las dos consultas del alta y no mucho más.

**Redis, no `lru_cache` con TTL manual.** El vencimiento vive del lado del
servidor de caché; reimplementarlo con una segunda estructura en memoria
—un dict con timestamps, o una librería de TTL-cache— es reinventar lo que
Redis ya hace con `EX`. Mismo criterio de fail-open que
`core/rate_limit.py`: un Redis caído no debe impedir la consulta, solo
perder la caché — la alternativa (fail-closed) bloquearía un alta por un
componente que solo existía para ahorrar plata.

**No cambia ADR-041.** La segunda llamada de `nombres_desde_dni`/
`razon_social_desde_ruc` sigue existiendo tal cual —la doble validación es
deliberada—; lo que deja de pasar es que esa segunda llamada vuelva a
salir a la red cuando el documento es el mismo que se acaba de consultar.

## Consecuencias

- `tests/conftest.py` gana `_cache_de_consulta_en_memoria` (autouse), mismo
  patrón que `_rate_limit_en_memoria`: cada test arranca con la caché
  vacía, para que el resultado de uno no contamine al siguiente que
  consulte el mismo número.
- Dos pruebas existentes asumían que consultar el mismo DNI dos veces
  seguidas tocaba la red dos veces —era exactamente el comportamiento que
  esto corrige—; se ajustaron para usar documentos distintos por vuelta
  donde ese era el punto real de la prueba (la cuota corta antes de llegar
  al proveedor), no un efecto secundario de la caché.
