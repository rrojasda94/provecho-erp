- **Lentitud y caídas del ERP y del sitio en staging** (2026-09-19). Tres
  causas juntas: la API corría con un solo proceso y el pool de conexiones por
  defecto de SQLAlchemy (5+10); las pantallas `/web/carta` y
  `/web/ingredientes` del ERP pedían las fotos con una petición por producto
  (hasta 200 a la vez, cada una con 3 consultas), lo que agotaba el pool
  (`QueuePool limit reached`); y la carta pública hacía una consulta de fotos
  por producto. Ahora: `GET /storefront/fotos/{entidad}?ids=` devuelve todas
  las fotos en una consulta y lo usan el ERP y la carta pública; el pool es
  configurable (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`); staging corre la API con 2
  procesos, Celery con `--concurrency 1` y un tope de memoria por servicio
  para que un proceso desbocado no tumbe el droplet; el sitio ya no espera
  indefinidamente a una API colgada (plazo de 8 s). Costo aceptado: el N+1 de
  precios de `precios.carta` sigue (deuda de `sales`).

- **Categorías de la carta del sitio salían sin nombre** (2026-09-19).
  `carta_publica` descartaba `categoria_nombre`, así que los chips eran
  puntos vacíos. Un test lo cubre.

- **El repartidor no veía nombre ni teléfono de quien pidió por la web sin
  cuenta** (2026-09-19). El teléfono se guardaba en `storefront_pedido` pero
  nunca llegaba a `sales`, y `delivery` lee el contacto del `cliente`. Ahora
  el evento lo lleva y la venta se ata a un cliente por teléfono (el
  existente o uno nuevo con nombre y teléfono). Además el aviso por WhatsApp
  deja de marcarse `SIN_TELEFONO`.

- **El tiempo de espera del sitio quedaba en 70-80 minutos** (2026-09-19). La
  carga de cocina contaba toda venta `orden` de la sucursal sin límite de
  tiempo, así que pedidos de prueba nunca cerrados inflaban la cola para
  siempre. Ahora solo cuentan las de las últimas 3 horas. (El estimado por
  tiempo de preparación de cada producto viene en un cambio aparte.)

- **"Trabaja con nosotros" confundía API caída con "sin vacantes"**
  (2026-09-19), y el tablero de contratación del ERP decía "ninguna
  convocatoria abierta" aunque listaba borradores y cerradas. Ahora el sitio
  avisa que no pudo cargar, y el ERP explica que solo las **publicadas** con
  fecha vigente salen en la web.
