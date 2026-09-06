# Historial — Calidad, revisión y auditorías transversales

Estado vigente: 🔶 En curso — rondas periódicas de auditoría transversal, la
última fue Ola 4 (2026-09-05)

Este archivo reúne, verbatim y en el orden en que aparecían en `ROADMAP.md`,
las rondas de auditoría/revisión de calidad y los parches surgidos de turnos
de prueba en staging. No son trabajo de un solo módulo: son pasadas
transversales que revisaron varios módulos a la vez, encontraron bugs reales
y los corrigieron. Sirven de constancia de la metodología ("cerrar TODO el
ERP antes de probar, no parchear a medias") y de las rondas Ola 1 a Ola 4.

## Cronología

### Parche del PDV — hallazgos del turno de prueba (0.7.8, desde 2026-08-28)

Se probó el PDV en producción con dos usuarios nuevos de trabajadores en CH1
y CH2, y salieron doce cosas. Tres causas raíz explican la mitad: el frontend
nunca renovaba el token, el PDV leía su sucursal del JWT congelado, y el
borrador no existía fuera de la memoria del navegador.

| Tanda | Qué | Estado |
|---|---|---|
| 1 | Sesión que se renueva sola + sucursal fresca con selector (ADR-073) | ✅ 2026-08-28 |
| 1 | Borrador del PDV en el servidor (ADR-074) | ✅ 2026-08-28 |
| 1 | El aumento es una tanda propia en el KDS (ADR-075) | ✅ 2026-08-28 |
| 1 | La cuenta de mesa recuerda su número (`VentaOut.mesa_numero`) | ✅ 2026-08-28 |
| 1 | Apertura/cierre de caja sin texto montado; el PDV cabe en la ventana | ✅ 2026-08-28 |
| 1 | Bloqueo manual de la pantalla (RN-POS-014) | ✅ 2026-08-28 |
| 1 | Alta de cliente con solo DNI, y reuso si esa persona ya es cliente | ✅ 2026-08-28 |
| 2 | Pantalla de despacho como overlay dentro del PDV | ✅ 2026-08-28 (salida rotulada «Volver al PDV» el 2026-08-30: la × sin etiqueta no se leía como la vuelta) |
| 2 | Cupón y descuento manual en caja (backend ya existía, faltaba el PDV) | ✅ 2026-08-28 |
| 2 | Notas de cocina: por línea **y** una general del pedido, al pie de la pastilla del KDS | ✅ 2026-08-28 |
| 3 | Motor de promociones automáticas + su pantalla en el back office (ADR-076) | ✅ 2026-08-28 |

La tanda 3 es un slice, no un parche: el motor de promociones condicionales
no existe —lo que hay es `promocion_cupon` (ADR-061), que hace otra cosa— y
tiene que soportar N×M, X unidades de un producto o categoría, combo, monto
mínimo y vigencia por día/hora. **No puede escribir en `venta.descuento_*`**:
esos campos son el acto humano firmado, y mezclarlos haría imposible auditar
qué descuento fue manual y cuál automático.

### Parche desplegables con búsqueda (versión a definir, 2026-08-29, en curso)

Nota de versión: al escribir esto se apuntó a "0.8.2", pero para cuando se
integró con `main` esa versión ya la había cortado otra rama con contenido
no relacionado (landing con dominio propio, marcaje de asistencia) y `main`
ya iba en 0.9.0. El corte de versión de este parche queda pendiente — se
hace al mergear, contra la versión real que tenga `main` en ese momento.

Reportado desde el uso: crear una promoción pedía teclear los identificadores
de los productos y categorías separados por coma. El campo era inusable —nadie
se sabe un UUID— y fallaba en silencio: un id mal copiado creaba la promoción
apuntando a un producto inexistente, que simplemente no se aplicaba nunca.

Al revisarlo, el problema era más ancho: **114 `<select>` en 50 archivos y
ninguno con búsqueda**. Y como `PAGE_SIZE_DEFECTO` es 50 y ningún `page.tsx`
pide más, varios desplegables muestran solo la primera página del catálogo sin
avisar que hay más — eso ya no es incomodidad, es un dato que falta.

Se migran los **62** desplegables alimentados por la API. Los 52 restantes son
enumerados escritos en el código —estados, tipos, modalidades, paginación— y
siguen siendo `<select>` nativos: ponerle un buscador a tres opciones estorba.

| Fase | Qué | Estado |
|---|---|---|
| 1 | `components/ui/combobox` (búsqueda, selección múltiple con fichas) sobre Base UI, con el filtrado en `lib/filtrar-opciones` | ✅ 2026-08-29 |
| 1 | Promociones: productos, categorías y el producto gratis dejan de pedir ids a mano | ✅ 2026-08-29 |
| 1 | `GET /inventory/articulos?q=` — el único catálogo que no entra completo en una página | ✅ 2026-08-29 |
| 2 | Listas largas (artículos, recetas, cuentas contables, proveedores) + `page_size` explícito donde hoy se trunca | ✅ 2026-08-29 |
| 2 | `?tipo=` repetible en artículos: "qué se produce" son subrecetas **y** mercadería | ✅ 2026-08-29 |
| 3 | Listas acotadas (sucursales, almacenes, marcas, unidades de medida, roles, grupos, divisas, atributos) | ✅ 2026-08-29 |
| 3 | Ayudante `elegirEnLista` en `e2e/util`: las pruebas dejan de hablar `selectOption` | ✅ 2026-08-29 |

Quedan **52** `<select>` nativos y son todos de enumerados escritos en el
código. No es deuda: un buscador sobre tres opciones estorba.

Decisión: el filtrado ocurre **en el cliente**, sobre lo ya cargado. Solo los
artículos buscan contra el servidor, porque son los únicos que no caben en el
techo de 200 filas por página. Añadir `?q=` a los otros tres endpoints que se
habían previsto resultó innecesario: SKUs y cuentas contables se devuelven sin
paginar y proveedores entran de sobra.

### Parche 0.8.1 — segundo turno de prueba en staging (2026-08-28)

Con la 0.8.0 ya en staging, el turno reportó seis cosas. Cinco son agujeros
que abrió la propia 0.8.0 —las notas de cocina estiraron las tarjetas del
KDS, los cupones y descuentos metieron una diferencia entre el total del
navegador y el del servidor, el overlay de despacho dejó al KDS suelto sin
salida— y la sexta, el cobro que rechazaba el monto exacto, llevaba ahí
desde que existe el cobro.

| # | Qué | Estado |
|---|---|---|
| 1 | El pedido sale de la cola de cocina al entregarse, no al facturarse; y la categoría sin estación cae en la primera (ADR-078) | ✅ 2026-08-28 |
| 1 | El aumento se vuelve idempotente (`venta_item.idempotency_key`) | ✅ 2026-08-28 |
| 2 | La plata se cuantiza a centavos en `rules.a_centavos`, en dominio y frontend | ✅ 2026-08-28 |
| 2 | El saldo lo dice el servidor: `GET /ventas/{id}/saldo` | ✅ 2026-08-28 |
| 2 | El efectivo admite sobrepago y el vuelto se guarda (`pago.vuelto`, ADR-077) | ✅ 2026-08-28 |
| 3 | `GET /ventas/{id}/comprobantes`: uno por cuenta, imprimibles desde el PDV | ✅ 2026-08-28 |
| 4 | Salida del KDS en las cuatro pantallas (el overlay del PDV sigue con su ×) | ✅ 2026-08-28 |
| 5 | Techo a la tarjeta del KDS: solo scrollea la lista, el pie queda a la vista | ✅ 2026-08-28 |
| 6 | Despacho lee el estado de la línea, no la ausencia de estación; lo listo se agrupa arriba | ✅ 2026-08-28 |

Lo que **no** se hizo y se decidió no hacer: entrega parcial de líneas. La
unidad de despacho sigue siendo el pedido (ADR-044, RN-CUP-004) — la
trazabilidad que pedía el mozo se resuelve mostrando qué está listo, no
partiendo la bolsa. Y el comprobante sigue siendo por cuenta y no por pago:
un pago parcial no tiene líneas propias que declarar a SUNAT.

### Parche compras/inventario (2026-08-29)

Reporte del usuario: no se podía crear un borrador de OC, el selector de
artículos no mostraba todo el catálogo (se replicaba en compras), la OC era
100% inmutable incluso en borrador, y no había forma de registrar una compra
a partir de solo una factura (sin OC previa). Investigación con 3 agentes
Explore confirmó causa raíz de cada uno con evidencia de código; el
descuento de stock por venta (que también se reportó como roto) resultó
estar correctamente implementado y testeado — se le agregó visibilidad en
vez de tocar la lógica.

| # | Qué | Estado |
|---|---|---|
| 1 | Rol `comprador` sin `inventory.leer`: tumbaba la pantalla entera de nueva OC | ✅ 2026-08-29 |
| 2 | Selector de artículos truncado a 50 (paginación sin `page_size`), en inventario, OC e importador de recetas | ✅ 2026-08-29 |
| 3 | OC editable mientras está en `borrador` (`PATCH`); inmutable desde `emitida` como ya era | ✅ 2026-08-29 |
| 4 | Compra directa sin OC previa, reutilizando `orden_compra` (ADR-081) | ✅ 2026-08-29 |
| 5 | KPI de incidencias de inventario en el dashboard (el descuento de stock ya funcionaba y estaba testeado) | ✅ 2026-08-29 |
| 6 | Alerta de stock bajo en el PDV, sin bloquear la venta (`GET /carta` → `stock_bajo`) | ✅ 2026-08-29 |

Lo que **no** se hizo y quedó como deuda (`docs/roadmap/deuda/modulo-purchases.md`):
la reconciliación completa estilo Odoo 18 entre compras/inventario/
contabilidad (más allá de los eventos puntuales que ya existen) y la caja
chica que la compra directa todavía no usa para pagar.

### Auditoría del 2026-08-20 — Ola 1, lo que toca ventas (2026-08-30)

La auditoría de las cinco fases dejó 18 hallazgos priorizados. Esta tanda toma
los tres que caen sobre `/ventas` —la pantalla que verifica lo que se
facturó— y los cierra. El patrón común no es un error visible sino silencio:
un filtro que devuelve cero filas, un botón que termina en 403, una venta que
parece no tener líneas.

| # audit | Qué | Estado |
|---|---|---|
| 1 | El filtro de estados de la jornada ofrecía `entregada` (no existe) y escondía `facturada`; `estado` viajaba como `str` sin validar | ✅ 2026-08-30 |
| 3 | «Reintentar emisión», «Nota de crédito» y «Anular» gateados por permiso | ✅ 2026-09-04 — el resto de los botones-403 (pagos, asientos, trabajadores, artículos, devoluciones) se cerró en la Ola 2; la OC ya estaba gateada desde ADR-085 |
| 11 | El fallo al traer las líneas para la NC se distingue de una venta sin líneas | 🔶 parcial — `rechazarPagoAction` se cerró en la Ola 2; falta la carta del PDV |
| + | La alerta de pedido demorado nunca disparaba para un pedido sin cobrar: `ESTADOS_VIVOS` decía `confirmada`, que no es un valor de `estado_venta`, y omitía `orden` | ✅ 2026-08-30 |

La causa raíz de los tres primeros era la misma: los cinco valores de
`estado_venta` estaban escritos en cuatro lugares que no se importan entre sí.
Ahora hay **una** fuente, `sales.domain.rules.ESTADOS_VENTA`, de la que salen
el `Enum` de la columna, el `Literal` del query param y —con un test de
coherencia, extendiendo el patrón que la propia auditoría señalaba como
existente-pero-no-extendido (hallazgo 15)— el desplegable de la pantalla.

**Sigue abierto de la misma familia**, encontrado al hacer esto y sin tocar:
el PDV filtra su pestaña de cobrados por `estado="pagada"` a secas
(`use-datos-pdv.ts`), así que la venta se le cae de la lista en cuanto SUNAT
acepta y la mueve a `facturada` — mismo bug que ya se parcheó en el KDS
(0.8.1); `estado_emision="error"` es un valor de enum que `sales` nunca
escribe (sí `inventory`), y el botón «Reintentar emisión» se ofrece
justamente para `rechazado`/`error` —donde reintentar no sirve— y no para
`pendiente` con intentos acumulados, que es donde sí; y la reemisión del
comprobante corregido tras una NC de motivo 02/03 está documentada en tres
lugares y no existe.

### Parche 0.9.1 — tercer turno de prueba en staging (2026-08-30)

Siete reportes. **Cinco no eran código faltante en el backend**: eran
superficies que nunca se construyeron sobre endpoints que ya existían y ya
tenían pruebas verdes — el patrón que se repite desde la 0.8.0 y que este
parche corta. Los otros dos sí eran decisiones pendientes: cuánto dura una
sesión y de dónde sale la cuenta contable de lo que se compra y se vende.

| # | Qué | Estado |
|---|---|---|
| 2 | El dashboard ofrece el pase al BI (existía el módulo, faltaba el enlace) | ✅ 2026-08-30 |
| 6 | El despacho embebido en el PDV vuelve con un botón rotulado, no con una × muda | ✅ 2026-08-30 |
| 1 | Pantalla de stock (`GET /inventory/stock` no lo consumía nadie) y kardex (`GET /inventory/movimientos`, nuevo) | ✅ 2026-08-30 |
| 3 | La sesión muere con el navegador y a las 8 h quietas (ADR-084) | ✅ 2026-08-30 |
| 4 y 5 | Ciclo de la OC en pantalla y factura de proveedor completa (ADR-085) | ✅ 2026-08-30 |
| 7 | La cuenta contable se configura en la categoría y se hereda (ADR-086) | ✅ 2026-08-30 |
| + | Recargar el PDV vuelve al pedido que se estaba armando, no a la primera pestaña (lo encontró la suite `uso`, que estaba roja en `main` por esto) | ✅ 2026-08-30 |
| + | Entrada de stock manual: `/inventario/ajustes` solo aprobaba/rechazaba, sin forma de solicitar una — el formulario llama al mismo `POST /ajustes` que ya existía, y un artículo con lote puede declarar código y vencimiento al entrar | ✅ 2026-08-30 |

### Inventario operable de punta a punta (2026-09-04)

Cuarto turno de prueba en staging: el módulo seguía inutilizable después de
arreglar los artículos sin SKU. **Una sola causa, anterior a todo lo demás**:
la fila de `stock` nacía sola con el primer movimiento, así que un almacén
recién dado de alta era invisible y no había cómo arrancar. Y otra vez el
patrón que se repite desde la 0.8.0 — endpoints entregados y probados, sin
pantalla que los llame.

| # | Qué | Estado |
|---|---|---|
| 1 | Un almacén declara qué artículos maneja (fila en cero) y con cuánto arranca (`carga_inicial`, sin segundo aprobador y solo sin historia previa) | ✅ 2026-09-04 |
| 2 | El conteo ya tiene qué contar; el mensaje vacío deja de mentir ("no hay stock con esos filtros" cuando no había nada declarado) | ✅ 2026-09-04 |
| 3 | Despacho de un requerimiento aprobado, con pantalla de picking y cantidad por línea | ✅ 2026-09-04 |
| 4 | Pantalla de Traslados y recepción — lo despachado quedaba `en_transito` para siempre | ✅ 2026-09-04 |
| 5 | `GET /solicitudes?almacen_abastecedor_id=`: la bandeja del que despacha, que no se podía preguntar | ✅ 2026-09-04 |
| 6 | El seeder crea `almacen1` y `aprobador1`: sin dos usuarios el circuito no cierra ni para probarlo | ✅ 2026-09-04 |
| + | El tipo de documento de una persona: «RUC» en el alta devolvía 500 y dejaba la fila ilegible (migración `c9f4a2e70b18`, vocabulario único en `src/shared/documento.py`) | ✅ 2026-08-30 |

### Auditoría del 2026-08-30 — Ola 2 (2026-09-04)

La auditoría backend↔frontend del 2026-08-30 dejó 18 hallazgos repartidos en
cuatro olas: [`docs/roadmap/auditoria-erp-2026-08-30.md`](../auditoria-erp-2026-08-30.md).
La Ola 0 (el inventario no se podía poblar) y las seis ramas de la Ola 1 ya
están en `main`. Ésta es la **Ola 2**: seis bloques, una rama y un PR cada uno.

Lo que une a los seis no es un error visible —es el patrón que la auditoría
vino a buscar—: un botón que promete 403, un formulario que se borra solo
cuando el servidor rechaza, un cuadre que dice «no cuadra» por un centavo que
no existe, una tablet de cocina que reintenta contra una sesión muerta para
siempre, y endpoints con ADR y pruebas que ninguna pantalla llama.

| Bloque | Hallazgos | Estado |
|---|---|---|
| `fix/contabilidad-pagos-rbac` | #3 ejecutar/rechazar pago sin gate + #4 diálogo con reset-on-error + #11 el rechazo descartaba su resultado | ✅ 2026-09-04 |
| `fix/contabilidad-asientos-rbac` | #3 «+ asiento manual» y «Anular» sin gate + #4 diálogo + #16 el cuadre se comparaba en `float` | ✅ 2026-09-04 |
| `fix/rbac-botones-resto` | #3 los botones de trabajadores, artículos y devoluciones (la OC ya estaba gateada desde ADR-085) | ✅ 2026-09-04 |
| `fix/sesion-expirada-cliente` | #10 la sesión muere y el cliente no se entera: bucle del KDS, campana muda, borradores del PDV que dejan de guardarse en silencio (ADR-088) | ✅ 2026-09-04 |
| `fix/dialogos-migracion-sweep` | #4 los diálogos restantes migran a `DialogoFormulario`: 9 archivos, 15 diálogos, más el clon privado del tablero de contratación | ✅ 2026-09-04 |
| `feat/inventario-transferencias-mermas` | #13 mermas y reservas sin pantalla; recepción parcial y traslado lateral sin entrada (el ciclo pedido lo cerró `fix/inventario-operable`) | ✅ 2026-09-04 — queda la guía de remisión, como deuda |

Tres correcciones al roadmap original, verificadas contra el código antes de
empezar: `fix/rbac-botones-resto` se achica porque
`compras/ordenes-compra/[id]` **ya está gateado** y es el modelo a copiar;
`gerencia/delivery` y `gerencia/kds` estaban en la lista del sweep sin tener
un solo `<dialog>`; y `feat/inventario-transferencias-mermas` está cumplido
solo en su tercio de transferencias.

### La contabilidad que no registraba, y la Ola 3 (2026-09-05)

Reportado operando en staging: **las ventas cerradas no aparecían en el
balance y la comida de personal no costaba nada**. La hipótesis era que
faltaba cablear algo, o que la facturación en pruebas solo reconoce
comprobantes oficiales.

No era eso, y vale escribirlo porque es el patrón que se repite: **el
cableado estaba completo y probado**. El asiento de la venta se genera al
confirmar la orden —del comprobante aceptado cuelga solo el IGV— y el de la
comida de personal existe desde ADR-034. Lo que fallaba es que el asiento
**se descartaba en silencio** por dos cosas que había que hacer a mano y
nadie sabía: importar el plan de cuentas y abrir el periodo del mes. Un mes
que nadie abría descartaba todos los asientos automáticos del ERP entero, y
el único aviso era un `log.info` que además decía el motivo equivocado.

| Bloque | Qué | Estado |
|---|---|---|
| `fix/contabilidad-no-asienta` | La empresa nace con su PCGE, el periodo se abre al primer asiento del mes, y la omisión queda en `asiento_omitido` con su motivo (ADR-089) | ✅ 2026-09-05 |
| `fix/contabilidad-cobro-y-anulacion` | El cobro cancela la `1212` y mueve caja/bancos según con qué se cobró; la venta anulada revierte su ingreso | ✅ 2026-09-05 — el incremento de una orden ya confirmada y la fecha del asiento quedan como deuda, ver `deuda/modulo-accounting.md` |

Y la **Ola 3** de la auditoría del 2026-08-30
([`docs/roadmap/auditoria-erp-2026-08-30.md`](../auditoria-erp-2026-08-30.md)):
cinco bloques, todos del mismo patrón que esta bitácora viene anotando desde
la 0.8.0 — endpoints entregados, probados y sin pantalla que los llame.

| Bloque | Qué | Estado |
|---|---|---|
| `feat/contabilidad-arqueos-libro-mayor` | Arqueos (con su `GET`, que faltaba), reglas de asiento, libro mayor navegable y detalle de asiento | ✅ 2026-09-05 |
| `feat/auditoria-pantalla` | `GET /api/v1/auditoria`: quién hizo qué, cuándo y con qué valor anterior | ✅ 2026-09-05 |
| `feat/rrhh-nomina-permisos-disciplina` | Legajo del trabajador (contratos, permisos, disciplina, certificados, pactos, boletas y liquidaciones en una lectura), bandeja de permisos y emisión de sanciones y certificados | ✅ 2026-09-05 — registrar boletas y liquidaciones queda como deuda: la nómina se calcula fuera del ERP |
| `feat/marketing-leads-encuestas-agencia` | Leads, encuestas y evaluación de agencias — con los tres endpoints de listado que faltaban y `encuesta_satisfaccion.empresa_id`, sin el cual no había filtro de tenant posible | ✅ 2026-09-05 — cargar opciones y firmar la decisión de agencia siguen por API |
| `feat/reports-matriz-edicion` | Áreas y miembros de distribución editables: el mapa mostraba los huecos y no había cómo taparlos | ✅ 2026-09-05 — editar reglas de distribución queda como deuda |

Fuera de alcance y anotado como deuda: préstamos, premios de concurso y
mover efectivo del banco a caja chica se registran por ahora con el asiento
manual —el cómo está en
[`docs/contabilidad/operaciones-no-operativas.md`](../../contabilidad/operaciones-no-operativas.md)—
porque el circuito de custodia de ADR-025 cuelga de una apertura de caja del
PDV y el efectivo que viene del banco no tiene dónde colgarse.

### Auditoría del 2026-08-30 — Ola 4, calidad (2026-09-05)

Cuatro bloques de baja urgencia y alto ruido acumulado. El primero ataca el
modo de falla más silencioso que quedaba: **una lista recortada se ve igual
que una completa**.

| Bloque | Qué | Estado |
|---|---|---|
| `fix/paginacion-server-side` | #14 el recorte se avisa en las nueve pantallas que traían 200 filas y paginaban en el navegador; `GET /inventory/lotes` gana tope | ✅ 2026-09-05 |
| `fix/contrato-tests-y-tipos-duplicados` | #15 una prueba parametrizada compara nueve listas de pantalla contra el enum del modelo —encontró una que ofrecía un valor que la API rechaza— y las formas `{id, nombre}` dejan de estar declaradas diecinueve veces | ✅ 2026-09-05 |
| `fix/accesibilidad-insignia-aria-live` | #17 ocho píldoras de estado escritas a mano pasan a `Insignia`, y el aviso pasajero del KDS y del PDV se anuncia también por voz | ✅ 2026-09-05 |
| `chore/limpieza-menor` | #18 el CDR se descarga y el permiso huérfano sale del seeder; la caducidad del secreto del terminal y los campos servidos de más quedan anotados con su motivo | ✅ 2026-09-05 |

### Catálogo modelo Odoo (0.7.0, en curso desde 2026-08-23)

Rama `feat/catalogo-odoo`, sobre v0.6.0. El catálogo pasa al modelo de
atributos y variantes de Odoo 18 porque el actual no soporta el carta real de
Charlie's: una `Pizza MitadxMitad Familiar` de 19 sabores por mitad son 361
productos con 361 recetas.

| Fase | Qué | Estado |
|---|---|---|
| F1 | Modelo, migración aditiva `e2b7c40d91af`, reglas puras | ✅ 2026-08-23 |
| F2 | Explosión de receta condicionada, venta, eventos, sync | ✅ 2026-08-23 |
| F3 | Conversor y cargador del catálogo de Odoo (`scripts/odoo/`) | ✅ 2026-08-23 |
| F4 | Matriz de recetas (ADR-057) | ✅ 2026-08-23 |
| F5 | Lienzo sobre el modelo de atributos (ADR-058) | ⛔ superada 2026-08-24 (ADR-063) |
| F6 | Seeder desde los `.xlsx` reales, corte 0.7.0 | ⏳ |
| F7 | La condición de una línea se lee y se edita en el lienzo | ⛔ superada 2026-08-24 (ADR-063) |
| F8 | Los atributos vuelven a la tabla: pantallas + generador de variantes (ADR-063) | ✅ 2026-08-24 |

**F5 y F7 quedaron sin efecto el mismo día que se cerraron**: el lienzo no
resultó un lugar de trabajo usable — el usuario seguía sin poder ver ni crear
atributos — y se reemplazó entero por `/catalogo/atributos` + la sección
«Atributos» de la ficha del producto + la columna «Condición» del editor de
receta. F8 cubre lo mismo que F5/F7 prometían, con tablas, y suma el
generador de combinaciones que F5 había dejado pendiente (`modo_variante =
'siempre'`; `'dinamica'` sigue sin construirse, ver deuda técnica).

**Vuelta atrás**: la migración de F1-F4 es solo aditiva, así que la imagen
0.6.0 corre contra ese esquema sin enterarse. F8 rompe esa promesa para
`producto_comercial.lienzo_pos` (migración `ce32c6610eb7`, la borra): volver
a una versión anterior a F8 exige `alembic downgrade` explícito, ya no basta
con `./scripts/desplegar.sh 0.6.0`.

## Fuentes

Texto extraído verbatim de `ROADMAP.md`, líneas 68-373 (estado del archivo al
2026-09-06, worktree `rrhh-remuneracion-token-supervisor-71b243`):

- Líneas 68-94 — Parche del PDV (0.7.8)
- Líneas 96-135 — Parche desplegables con búsqueda
- Líneas 137-162 — Parche 0.8.1
- Líneas 164-187 — Parche compras/inventario
- Líneas 189-220 — Auditoría del 2026-08-20, Ola 1
- Líneas 222-239 — Parche 0.9.1
- Líneas 241-258 — Inventario operable de punta a punta
- Líneas 260-287 — Auditoría del 2026-08-30, Ola 2
- Líneas 289-328 — La contabilidad que no registraba, y la Ola 3
- Líneas 330-341 — Auditoría del 2026-08-30, Ola 4
- Líneas 343-373 — Catálogo modelo Odoo (0.7.0)
