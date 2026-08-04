# ADR-024 — Catálogo cerrado de reportes y tableros guardados

- Estado: aceptado
- Fecha: 2026-08-04

## Contexto

El dashboard de ADR-012 es un agregado fijo: tres tarjetas (ventas del día,
stock bajo mínimo, cajas abiertas) sin filtros y sin forma de que el usuario
elija qué mira. El ROADMAP lo declaraba así explícitamente ("el dashboard de
hoy es mínimo (3 tarjetas)").

Lo pedido es otra cosa: **autoservicio de reportes**. Que gerencia arme sus
propias vistas, elija rangos de fecha (predefinidos o personalizados),
compare sucursales o grupos de sucursales, decida si un dato se ve como
tabla o como gráfico, ajuste el tamaño de cada tarjeta y **guarde esa
disposición** para volver a encontrarla.

La tentación evidente es un **constructor de consultas genérico**: que el
cliente mande tabla, columnas, agrupamiento y filtros, y el backend arme el
SQL. Es lo que hace un BI y resolvería de una vez todos los reportes
futuros.

## Decisión

**No hay constructor de consultas. Hay un catálogo cerrado**
(`src/core/reportes/catalogo.py`): una lista fija de reportes, cada uno con
su código, sus columnas declaradas, su visualización por defecto y la
función que lo resuelve.

El cliente manda un `codigo` del catálogo y filtros tipados (preset de
rango o fechas, `sucursal_ids`, `limite`). Nunca manda una tabla, una
columna, un `order by` ni nada que llegue a componer SQL.

Piezas:

- `core/reportes/catalogo.py` — el whitelist. Cada `Reporte` declara
  `permiso` (el de su **módulo dueño**), `columnas`, `visual`/`visuales`,
  `etiqueta`/`valor` (qué graficar) y `filtra_sucursal`.
- `core/reportes/rangos.py` — presets (`hoy`, `ultimos_30`, `mes_actual`,
  …) resueltos contra `fechas.hoy()`, más rango libre acotado a
  `MAX_DIAS = 731`.
- `core/reportes/router.py` — `GET /reportes` (catálogo ya recortado a lo
  que el usuario puede ver), `POST /reportes/{codigo}/datos`, y el CRUD de
  `/tableros`.
- `shared/models/tablero.py` — la disposición guardada (tarjetas y filtros
  en JSON, por usuario).

Vive en `core/` y no es un módulo nuevo, por la misma razón que
`dashboard_router`: **compone contratos públicos de varios módulos** y no le
pertenece a ninguno. Un módulo `reportes` implicaría los siete registros de
alta documentados en `module-guide.md` sin ganar aislamiento — el motor no
tiene dominio propio, solo ensambla `queries_publicas` ajenas.

### Por qué el catálogo y no el constructor

1. **Superficie de inyección.** Un armador genérico sobre el ERP entero es
   el punto más expuesto del sistema: cualquier error de escapado ahí lee
   toda la base. El catálogo no acepta identificadores del cliente, así que
   ese error no se puede cometer.
2. **Fuga de RBAC.** El permiso protege *recursos*, no *tablas*. Con un
   constructor genérico, quien puede "hacer un reporte" puede leer
   `boleta_pago` desde el reporte de ventas: el RBAC del ERP deja de
   aplicar en cuanto la consulta la escribe el cliente. Con el catálogo,
   cada reporte declara el permiso de su módulo dueño y un `comprador` ve
   compras sin ver ventas, sin una segunda matriz de permisos que mantener.
3. **Costo real.** Agregar un reporte es una entrada en una tupla más una
   función en el `queries_publicas` del módulo dueño. El constructor exige
   metamodelo, validador de identificadores, planificador de joins y
   límites de costo — meses, para un negocio que hoy tiene cinco reportes
   reales.

### Decisiones menores, con su motivo

- **El preset se guarda como código, no como par de fechas resuelto.** Un
  tablero guardado con "mes actual" tiene que seguir diciendo *el mes
  actual* la próxima vez que se abra, no el mes en que se guardó.
- **Sin selección explícita de sucursales no se devuelve "todas", se
  devuelven las del usuario.** Un cajero de Tarapoto que no toca el filtro
  ve Tarapoto. `None` (sin filtro) queda solo para el superusuario sin
  sucursales, que es la cuenta de setup.
- **Solo salen las columnas declaradas.** `ejecutar()` proyecta contra
  `reporte.columnas`, así que una consulta que devuelva de más (un `id`
  interno) no se filtra al cliente por olvido de nadie.
- **Los montos viajan como texto exacto**, no como float: un total en
  coma flotante pierde centavos al serializarse.
- **Las tarjetas de un tablero se validan al guardar** contra el catálogo
  *visible para ese usuario*. Si no, bastaría guardar una tarjeta de un
  reporte ajeno para saltarse el RBAC en la próxima carga.
- **`tarjetas`/`filtros` son JSON.** La forma de una tarjeta cambia con
  cada tipo de visualización nuevo; normalizarla obligaría a una migración
  por cada una. Lo que no es libre es el `codigo`, que sí se valida.

## Consecuencias

- Un reporte nuevo es una entrada en el catálogo + una función pública en
  el módulo dueño. No hay pantalla que tocar: el frontend arma la tarjeta
  desde el catálogo (columnas, tipos, visualizaciones admitidas).
- El frontend no mantiene una lista de reportes en paralelo. Si un reporte
  no llega en `GET /reportes`, es porque el usuario no puede verlo.
- **Lo que el usuario no puede hacer**: un reporte que nadie previó. Ese es
  el precio aceptado. Si aparece demanda real de exploración libre, el
  camino no es abrir el constructor sino exportar a una herramienta de BI
  con su propio control de acceso sobre una réplica de lectura.
- Los gráficos se dibujan sin librería: un ranking horizontal son divs con
  ancho porcentual y la serie es un `<polyline>` SVG. La frontera para
  meter Recharts está anotada en `components/reportes/graficos.tsx` —
  tooltips con hit-testing, ejes calculados, zoom o series apiladas.

## Alternativas descartadas

- **Constructor de consultas genérico**: descartado por 1, 2 y 3 arriba.
- **Módulo `reportes` propio**: descartado — sin dominio propio, solo suma
  los siete registros de alta de un módulo.
- **Un endpoint por reporte** (`/reportes/ventas-por-dia`, …): descartado.
  Multiplica el boilerplate de filtros y RBAC por reporte, y obliga al
  frontend a saber de antemano qué endpoints existen — justo lo que el
  catálogo evita.
- **Guardar el tablero en `localStorage`**: descartado. Se perdería al
  cambiar de equipo, y en un negocio con varias sucursales el gerente entra
  desde donde esté.

## Addendum (2026-08-04) — compartir, exportar, reordenar y caché

Se cerró en el mismo día la deuda que este ADR había declarado. Las
decisiones que agrega:

**Compartir por rol, no con una lista de personas** (`tablero.rol_id`,
migración `5e1c7775f6ca`). NULL = privado. Con rol, el tablero lo ve en
solo lectura cualquiera que lo tenga; editarlo y borrarlo siguen siendo del
dueño (`usuario_id`). Se eligió el rol sobre la lista explícita porque **se
administra solo**: alguien cambia de puesto y gana o pierde el tablero sin
que nadie recuerde actualizar nada, y un trabajador que cesa deja de verlo
al perder el rol — con una lista habría que removerlo de cada tablero, uno
por uno, y el que se olvide es una fuga.

Dos guardas: solo se comparte hacia un **rol propio** (si no, cualquiera
podría publicar en la bandeja de Gerencia sin pertenecer a ella — no es
fuga de datos, pero sí una vía para llenarle la pantalla a un área ajena),
y **compartir no expone nada**: cada tarjeta revalida el permiso de su
módulo al pedir sus datos, así que quien no tenga `purchases.leer` abre el
tablero compartido y esa tarjeta le responde 403. Lo que se comparte es la
disposición, no el contenido.

**Exportación a CSV en el cliente, no un endpoint.** Los datos ya están en
el navegador: un endpoint nuevo repetiría consulta, RBAC y rango para
producir exactamente las filas que la pantalla ya tiene. Se exporta lo que
se ve; para más filas se sube `limite` (tope 500, que es límite de
seguridad, no de UI). Los montos salen crudos (`1234.50`) porque
`S/ 1,234.50` no lo suma ninguna hoja de cálculo, y el archivo lleva BOM
UTF-8 — sin él Excel abre "Lácteos" como mojibake. Escapado RFC 4180: una
razón social con coma partiría la fila en dos columnas.

**Reordenar con HTML5 nativo.** No hace falta librería de drag-and-drop
para mover tarjetas dentro de una grilla. Cada tarjeta lleva un `uid`
estable **solo en el cliente** (no se persiste: el orden ya lo da el índice
del array guardado) para que la clave de React no sea la posición.

**Caché de 30 s por (reporte + filtros)**, en memoria del módulo. Un
reporte es una foto, no un dato editable, así que no hay nada que invalidar
salvo el paso del tiempo. Medido en navegador: reordenar dentro de la
ventana cuesta **0 peticiones**. Si algún día hace falta caché de verdad
—compartida entre usuarios, invalidada por evento— va del lado del
servidor con Redis, no acá.

**Tres reportes más**: `ventas_por_hora`, `ventas_por_trabajador` y
`margen_por_producto`. Dos notas de diseño que valen más que los reportes:

- *La hora es la del negocio.* Agrupar por hora se hace en SQL sobre UTC
  (`extract` es lo único portable entre SQLite y Postgres) y la etiqueta se
  corre después con `fechas.desfase_horas()`. Son 24 filas: reetiquetarlas
  es exacto y gratis, mientras que convertir cada venta antes de agrupar
  obligaría a traerlas todas. Vale porque Perú no tiene horario de verano;
  la función lo verifica y falla si la zona configurada tuviera un desfase
  que no sea de horas enteras.
- *Costo desconocido no es costo cero.* Un producto sin receta sale con
  `costo` y `margen` en `null`, no en 0 — cero mostraría 100 % de margen
  sobre un dato que en realidad falta. El costo se toma de
  `inventory.recetas.costo_linea` (que ya contempla merma) en vez de
  recalcularlo con otro criterio: dos pantallas del ERP no pueden mostrar
  números distintos para lo mismo.

## Referencias

- ADR-012 (dashboard gerencial original), ADR-004 (tenant desde el JWT),
  ADR-014 (parámetros por empresa).
- `docs/architecture/events.md` § contratos públicos de lectura.
- Tests: `tests/test_reportes.py`.
