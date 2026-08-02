# ADR-012 — Dashboard gerencial: agregador en `core` + slice mínimo de caja

- Estado: aceptado
- Fecha: 2026-07-26

## Contexto

Se pidió un dashboard gerencial mínimo (ventas del día, stock crítico,
caja) con login propio — primera pantalla real del frontend, que hasta
ahora era solo el scaffold de Next.js. Al explorar el backend aparecieron
dos huecos: `sales` no tenía ningún endpoint de listado de ventas (solo
`GET /ventas/{id}` puntual), y `accounting` tenía los modelos
`apertura_caja`/`cierre_caja`/`arqueo` (migrados desde 2026-07-20) sin
ninguna capa de aplicación ni endpoint — el ciclo de caja completo
(PROC-CTB-001/002) nunca se construyó.

## Decisión

**Dos piezas nuevas, alcance deliberadamente acotado:**

1. **Slice mínimo de caja** (`accounting.application.caja`): abrir, cerrar
   y arquear, con **reconciliación real** — el cierre no acepta un monto
   tipeado sin verificar, calcula `monto_esperado = monto_apertura +
   efectivo cobrado desde la apertura` y compara contra el conteo físico.
   Sin esa reconciliación, "cierre de caja" sería un formulario que guarda
   números sin ningún valor de control, lo que habría sido peor que no
   construirlo.
   **Explícitamente fuera de esta fase** (ver ROADMAP): las reglas
   RN-POS-009 a RN-POS-013 completas (verificación de series de POS,
   denominaciones obligatorias), el relevo autenticado por ambas partes con
   PIN (hoy se registra `relevo_encargado_id` sin exigir su propia sesión),
   la máquina de estados de `custodia_efectivo`, y el enlace con `sales`
   para bloquear el cobro sin caja abierta. Ese es un slice de negocio
   completo por derecho propio — construirlo entero *dentro* de un pedido
   de dashboard habría sido alcance no pedido.

2. **Agregador de dashboard en `core`** (`src/core/dashboard_router.py`),
   no en un módulo de negocio: compone lecturas de `sales`, `inventory` y
   `accounting` en una sola respuesta. Vive en `core` por la misma razón
   que `core/app.py` ya ensambla los routers de todos los módulos — es
   infraestructura transversal, no dominio de uno solo. Nunca importa el
   dominio de ningún módulo directo: llama a sus funciones
   `application`/`queries_publicas` ya pensadas para consumo externo,
   agregando dos nuevas a `sales.application.queries_publicas`
   (`resumen_ventas_del_dia`, `puntos_venta_de_empresa`) e `inventory`
   (`contar_bajo_minimo`) siguiendo el patrón ya establecido
   (`listar_clientes_para_analisis`).

## Consecuencias

- **`accounting` consulta a `sales` en tiempo real** (no solo vía eventos):
  `total_efectivo_cobrado` y `puntos_venta_de_empresa`. Primera vez que un
  módulo usa el contrato de lectura de otro de forma síncrona para una
  operación de escritura propia (cerrar caja), no solo para un reporte —
  precedente a tener en cuenta si aparece otro caso similar.
- El dashboard usaba `empresa_id` como query param, no derivado del JWT —
  deuda declarada en ADR-004 y **saldada el 2026-08-01**: hoy exige la
  empresa del JWT (`tenant.empresa`), y el query param solo lo puede usar un
  superusuario sin empresa asignada. Se exige *una* empresa, no
  `filtro_empresa`: sumar ventas de dos empresas distintas no significa nada.
- Sin `sync_outbox` ni caché: cada llamada al dashboard recalcula todo en
  vivo. Aceptable al volumen de un grupo de restaurantes chico; revisar si
  el agregado empieza a pesar.
- Nuevos permisos: `dashboard.leer`, `accounting.caja_operar`,
  `accounting.arqueo_registrar` — el cajero abre/cierra su propia caja sin
  necesitar permisos de administración general.
- Primer flujo de login real del frontend construido contra este
  dashboard — decisiones de UI (framework de estado, manejo de sesión) se
  registran en su propio ADR si el frontend crece más allá de esta
  pantalla.

## Alternativas descartadas

- **Construir el ciclo de caja completo** (relevo con PIN, denominaciones,
  custodia como máquina de estados) — descartado para esta fase: es un
  slice de negocio del tamaño de los ya construidos para `sales`/
  `purchases`/`production` cada uno en su propia sesión dedicada. Meterlo
  entero bajo "hacer un dashboard" habría distorsionado el pedido original.
- **Cierre de caja sin reconciliación** (guardar el monto tipeado tal
  cual) — descartado: un cierre de caja que no verifica nada no es un
  control, es un formulario. El costo de calcular `monto_esperado` es una
  función más, no otro slice.
- **Endpoint de listado de ventas genérico** (`GET /ventas?fecha=...`) en
  vez de un resumen agregado — descartado para el dashboard: lo que la
  vista gerencial necesita es cantidad+total, no la lista completa. Un
  listado paginado de ventas queda como pendiente de API general (ver
  ROADMAP → Contrato de API), no se resuelve de paso acá.
