# Modelo del dominio

Entidades del negocio y sus relaciones, independientes de la tecnología.
Solo describe **qué existe y cómo se relaciona**; las validaciones, cálculos y
políticas viven en [business-rules.md](business-rules.md), y los principios
invariantes en [../foundation/business-philosophy.md](../foundation/business-philosophy.md).
Terminología oficial: [../foundation/glossary.md](../foundation/glossary.md).
Organización y visión en [../foundation/vision.md](../foundation/vision.md);
tablas en [../architecture/data-model.md](../architecture/data-model.md).

## Productos (separación obligatoria)

| Concepto | Qué es | Ejemplo |
|----------|--------|---------|
| **Insumo** | Artículo inventariable que se compra a un proveedor; ingrediente de receta; tiene costo promedio | Harina, queso, caja de pizza |
| **Subreceta** | Artículo inventariable que se fabrica (tiene su propia receta/BOM) | Masa, salsa madre |
| **Mercadería** | Artículo inventariable de venta directa, sin transformar; se comercia desde el punto de venta | Bebida embotellada |
| **Receta** | Lista de insumos/subrecetas con cantidades y mermas | Receta de pizza americana |
| **Producto comercial** | Lo que se vende en el PDV; apunta a una receta | "Pizza Americana Familiar" |

Distinción central: el producto comercial no es el artículo inventariable
(la regla que lo gobierna está en business-rules).

Una receta puede marcarse **flexible**: permite ajustar insumos por sabor
o calidad; el criterio de ajuste lo asigna el área de Producción
(RN-PRD-010).

### Modificadores y variantes

Un producto comercial puede tener **modificadores**: tamaño, combinación
(otro sabor/elemento), extras, restas. Cada modificador es en sí una
"receta" que altera la receta base y, por tanto, el costo y el producto
resultante. El sistema siempre los calcula en este orden — sin importar en
qué orden los elige el cliente/trabajador —, porque cada paso depende del
resultado del anterior:

1. **Tamaño** — centra la base del producto.
2. **Combinación** — aplica la receta de cada elemento/sabor elegido.
3. **Extras** — se aplican sobre el tamaño ya elegido.
4. **Restas** — quitan del total la cantidad completa del insumo no deseado.

Un producto puede no tener alguno o ninguno de estos tipos, según su
configuración. El resultado de aplicar modificadores es una **variante de
producto**: un producto comercial final, con receta y precio propios.

Ejemplo: pizza de 2 sabores → 1) tamaño (centra la base) → 2) combinación
(receta de cada sabor elegido) → 3) extras (sobre ese tamaño) → 4) restas
(insumos no deseados).

### SKU

Código alfanumérico interno e inmutable (nunca se elimina, es parte del
historial de movimientos del grupo) que da seguimiento a un artículo
inventariable y sus variantes intercambiables. Un mismo artículo (ej.
"Harina de Trigo") puede tener varios SKU — uno por marca/proveedor
admitido —, priorizados entre sí con un criterio configurable por producto
(precio, disponibilidad, tamaño, calidad, u otro; no es un criterio fijo).

Una receta puede admitir varios SKU de un mismo artículo: al consumir,
descontar o solicitar, el sistema usa el SKU disponible según su
prioridad. Si el SKU principal llega a su stock mínimo, se genera una
alerta; si no hay disponibilidad, se solicita a un proveedor un SKU
alternativo — este solo se usa mientras dure la indisponibilidad del
principal, y su abastecimiento retira la alerta del SKU principal.

Formato: solo letras mayúsculas sin tildes (UTF-8), números naturales y
guion como separador; nomenclatura y formato los define el área de
compras del grupo empresarial. Es obligatorio asignar un SKU al ingresar
un producto inventariable nuevo. No reemplaza la búsqueda por QR, código
de barras o nombre comercial.

### Subreceta

Receta que produce un artículo inventariable (a diferencia de la receta de
un producto comercial, que produce un ítem vendible). El artículo
resultante puede encadenarse: consumirse como ingrediente de otra
subreceta (BOM multinivel) o de la receta final de un producto comercial.
Funciona igual que una receta (ítems, cantidades, mermas — ver Receta).

Ejemplo: Masa de pizza fresca (harina + levadura + sal → masa fresca) →
Masa precocida de pizza familiar (masa fresca + ... → masa precocida) →
Pizza (masa precocida + ... → producto comercial "Pizza Familiar").

Recetas y subrecetas se crean/modifican en el ERP por el área de
Producción o I+D (RN-PRD-008); toda modificación genera reporte, actualiza
costos, genera solicitud de actualización de manuales de recetas y
notificación urgente a los involucrados en su fabricación (RN-PRD-009).

### Lote

Conjunto de artículos fabricados bajo condiciones idénticas (misma
elaboración); identificado con un código único asignado por el ERP, según
nomenclatura definida por el área de Producción (paralelo al SKU, que lo
define compras). Registra fecha, manipulador, envasador, timestamps,
lugar de elaboración, línea de producción, y toda variable documentada
durante el proceso (ej. qué insumos se modificaron, si la receta era
flexible) — trazabilidad completa desde la fabricación hasta el
consumo/venta.

Se imprime en la etiqueta de cada artículo producido en el lote. La
etiqueta incluye: cantidad, unidad de medida, código de barras/QR, número
de lote, fecha de vencimiento, y condiciones de almacenamiento y
transporte.

### Fecha de vencimiento y código de barras/QR

La fecha de vencimiento (ligada al Lote) tiene tres orígenes: producto
elaborado en cocina de producción → se determina según normativa vigente
y análisis de laboratorio propio del producto resultante; producto
comprado a proveedor → viene con la fecha declarada por el proveedor;
producto abierto/en uso en sucursal → vida útil adicional desde la
apertura, hasta 7 días en refrigeración (~4°C promedio) o hasta 2 meses
congelado (-18°C).

El código de barras/QR identifica el SKU para lectura rápida en almacén/
POS; no todo artículo lo tiene. Los productos de cocina de producción
usan un QR generado por el ERP que codifica SKU + Lote juntos (no solo el
SKU). No reemplaza la búsqueda por nombre comercial (ver SKU).

### Servicio

Producto comercial intangible: satisface la necesidad del cliente
consumiendo recursos (tiempo, horas/hombre, u otros), sin apuntar a una
receta de insumos ni ser inventariable. No confundir con "servicio al
cliente" (atención). Pertenece a una marca, igual que un producto
comercial.

El costeo depende de la naturaleza del servicio (fórmula propia por tipo).
Ejemplo, delivery: horas/hombre + desgaste de vehículo + combustible
consumido; se cobra al cliente en tarifa según distancia. El grupo
empresarial planea ofrecer más servicios aún no determinados; cada uno se
cotiza en el área comercial sumando al costeo un margen de contribución y
un % de cobertura de emergencias.

### Empaque

Tipo de artículo inventariable usado para el traslado del producto
comercial (mesa, takeout, delivery); no es ingrediente de receta —no se
incluye en `receta_item`. Se compra a un proveedor; lead time típico mayor
a 15 días entre cotización aceptada y recepción, exige compra planificada
con anticipación. También se consume directo en el almacén central para
envíos especiales.

Su consumo por venta se configura en el producto comercial: un `empaque_id`
+ checkboxes de modalidad (mesa / takeout / delivery) que indican en
cuáles se descuenta stock. Ejemplo Charlie's Pizzas: la pizza familiar no
consume caja en mesa, pero sí en takeout y delivery (caja 35x35). No
aparece en el comprobante de la venta que lo consume, salvo que el cliente
lo compre como producto comercial independiente — solo disponible en POS
operado por trabajador, no en kiosko ni web.

Ejemplos: envases, cajas, bolsas, recipientes.

## Activos

Todo recurso o bien con valor económico para la empresa o el grupo
empresarial. Tres tipos:

- **Corriente**: líquido, alta rotación; se busca convertir en liquidez
  económica. Es el `artículo` inventariable (`insumo`, `subreceta`,
  `mercadería`) — insumos para recetas, mercadería de venta directa
  (bebidas embotelladas), empaques.
- **No Corriente**: vida útil mayor a un año; sujeto a la propiedad de una
  empresa. Equipamiento, vehículos, mobiliario, computadoras, terrenos,
  locales. Vive en el Almacén Virtual de Activos (ver más abajo).
- **Intangible**: propiedad del Grupo Empresarial, no de una empresa
  individual. Marcas, patentes, software, procesos. Se comercializa vía
  licenciamiento/franquicia (ver [Marca](../foundation/vision.md#marca));
  documentado y registrado. Su venta requiere aprobación unánime de la
  sociedad (RN-GRP-006).

### Vehículo

Tipo de Activo No Corriente que sirve para transportar personas y
productos. Depreciable; requiere combustible y mantenimiento para operar.
Pertenece a una flota (moto, carro, camión, etc.); tiene placa de rodaje,
números de serie de motor y chasis, registro de kilometraje (da fe del
buen uso y de las rutas establecidas), cámaras y rastreador GPS.

Se asigna a un transportista o responsable, quien rinde cuentas del uso y
de posibles daños o pérdidas. Puede ser alquilado (si la empresa no
quiere aumentar activos ni correr con sus gastos), o licenciado a un
trabajador como beneficio laboral durante su estadía en la empresa. Su
adquisición la ve el área de compras, con aprobación de gerencia y del
área contable/financiera. Al cumplir su vida útil, puede venderse (solo
depreciado al 100% + acta, RN-ACT-001).

> **Herramienta** es un término coloquial, no una entidad propia: se
> refiere a cualquier Activo o utensilio que un trabajador usa para
> realizar su trabajo (puede ser Equipamiento, Vehículo, o un utensilio).

### Mantenimiento

Acción rutinaria que garantiza la operatividad de un vehículo,
equipamiento o local. Aumenta su vida útil y evita el malfuncionamiento.
Se programa y coordina con un proveedor de servicios; cada activo tiene
su frecuencia recomendada de mantenimiento.

Puede adelantarse si el personal que lo opera reporta desperfectos o una
baja de productividad del equipo; ese reporte se hace al área de compras
y al área contable, para coordinar.

### Repuesto

Tipo de artículo inventariable (vive en almacén o se compra a proveedor)
usado para reparar o repotenciar equipamiento y vehículos.

Tiene un stock mínimo según la frecuencia o urgencia de su uso: piezas
baratas y de fallo frecuente (ej. condensadores de un horno) se
mantienen en stock; piezas caras o lentas de conseguir pero fundamentales
y que no se deterioran almacenadas (ej. un chispero) se mantienen siempre
con 1 unidad disponible.

Su instalación la realiza el servicio técnico de terceros, la garantía
del proveedor, o personal propio. Debe tener número de serie o modelo
compatible con el equipo/vehículo al que corresponde. Su adquisición es
responsabilidad del área de compras y del área de almacén. Puede usarse
para repotenciar un equipo degradado, aumentando así su vida útil (no
solo para repararlo).

### Equipamiento

Tipo de Activo No Corriente de larga duración que permite a los
trabajadores producir y cumplir su trabajo: computadoras, mesas y
armarios refrigerados, hornos, mobiliario de acero inoxidable,
refrigeradoras, congeladoras, microondas, licuadoras, laptops, tablets,
pantallas, etc.

Requiere mantenimiento y repuestos; es responsabilidad de una empresa.
Puede ser alquilado o adquirido. Tiene número de serie y se etiqueta,
para facilitar el reporte de mantenimiento y el seguimiento en
auditorías. Los trabajadores que lo usan deben recibir inducción de uso y
reportar averías.

Los daños físicos, el robo de piezas, la sobrecarga o el maltrato del
equipo son responsabilidad del trabajador que lo opera; según la
gravedad, se eleva un reporte a RRHH, que notifica con un memorándum o
una sanción (ver plantillas RRHH). Se audita de manera rutinaria; vive en
el Almacén Virtual de Activos; puede tener categorías, igual que
productos o vehículos.

Todo Activo (artículo, activo no corriente, producto comercial, servicio)
lleva un `id_interno`: 4 caracteres alfanuméricos, autogenerado por el ERP
al crearse, inmutable e irrepetible — distinto del `id` UUID y del SKU
(que es solo de artículo). Al darse de baja o descontinuarse, un Activo se
archiva (se oculta de listados); nunca se elimina de la base de datos
(RN-GEN-005/006).

### Categoría

Agrupador de artículos y activos (insumo, subreceta, mercadería, empaque,
embalaje, limpieza, menaje, equipamiento, artículos de oficina, uniformes,
etc.), para su gestión operativa y contable. Aplica a todo Activo, no solo
al `artículo` inventariable.

Se crea a nivel **empresa** (no a nivel grupo empresarial, a diferencia
del artículo/producto comercial); cada empresa organiza sus categorías
según su conveniencia. Su creación depende del área de compras y del área
contable. Puede ligarse a un asiento contable, configurable por tipo de
movimiento (compra, consumo, merma, etc.). Es opcional para un
artículo/activo, pero se recomienda por orden. Los artículos pueden
reorganizarse entre categorías; las categorías se pueden eliminar y
renombrar (a diferencia del SKU, que nunca se elimina).

### Unidad de Medida

Unidad concreta para calcular la cantidad de un artículo. Pertenece a una
**Categoría de UdM** (peso, volumen, distancia, energía, datos, unidades...)
que define una unidad base de referencia; cada UdM de la categoría se
expresa como un ratio de conversión respecto a esa base (modelo tipo Odoo
— incluye lo que sería "conversión de unidades", no es un concepto
aparte). Unidad por defecto: "Unidades" (categoría discreta).

Ejemplos: categoría Peso (base Kilo) → Doypack 2kg, ratio 2:1 (1 doypack
en almacén = 2kg disponibles en receta). Categoría Volumen (base Litro) →
Botella 500ml, ratio 1:2 (1 botella = 0.5L). Al asignar UdM a una receta o
producto comercial, solo se sugieren UdM de la categoría del artículo (un
doypack 2kg admite "1 doypack 2kg" o "2kg", nunca "2 unidades" ni "2
litros").

Cambiar la UdM de un artículo no es recomendable; si se hace, primero se
modifica en las recetas que lo usan y luego en el artículo/producto,
genera un reporte de auditoría, y durante la transición el artículo queda
desactivado en recetas, requerimientos y ventas. Responsabilidad del área
de compras y contabilidad.

## Inventario

Lista detallada, ordenada y valorada de los activos de la empresa
(existencias por almacén). Registra existencias, optimiza costos y
garantiza disponibilidad de SKUs; apoya a contabilidad, producción,
comercial y financiera. Auditable, para prevenir robos, pérdidas y malas
prácticas de rotación.

Solo usuarios autorizados operan inventario, con niveles de acceso
configurables por rol:

- **Alcance**: solo su sucursal, o toda la empresa (seleccionable).
- **Visibilidad**: ver niveles de stock esperado, o inventario "a ciegas".
- **Acción**: solo conteo / conteo + requerimiento / solicitar ajuste /
  autorizar ajuste — quien solicita un ajuste no es necesariamente quien
  lo autoriza (separación de funciones).

Periodicidad de conteos y niveles de acceso son configurables en el ERP.

### Stock

Cantidad de unidades de un artículo dentro de un almacén, expresada en su
Unidad de Medida. Permite conocer la cantidad disponible para tomar
decisiones de almacenamiento (reposición, alerta, traslado).

- **Stock Mínimo**: cantidad mínima que debe mantenerse para cubrir un
  período de tiempo determinado.
- **Stock Máximo**: cantidad máxima admitida, para evitar desbordar el
  almacenamiento o generar pérdidas por falta de rotación/vencimiento.

Cada artículo tiene sus propias reglas de mínimo/máximo, determinadas por
las áreas de Producción, Contabilidad y Logística.

**Punto de Reorden**: fórmula concreta del stock mínimo — (demanda diaria
× tiempo de entrega en días) + stock de seguridad (por defecto, stock de
seguridad = demanda diaria; ajustable a futuro). Genera alertas de
reabastecimiento para sucursales, almacén central o de producción.

### Stock Disponible y Stock Reservado

**Stock Disponible**: porción del stock físico de un almacén que aún
puede solicitarse (stock total menos stock reservado).

**Stock Reservado** (= Stock Comprometido): porción restringida a favor de otro almacén o receta
que la solicitó; sigue físicamente en el almacén de origen — aún no
pickeada ni despachada (distinto de "en tránsito", que ya salió
físicamente). Si la solicitud o pedido que la originó se cancela o
modifica, el stock reservado vuelve a estar disponible automáticamente.
En el almacén central, un usuario autorizado puede liberar manualmente
una reserva y redistribuirla entre otros solicitantes, ante
desabastecimiento o sobredemanda del SKU.

### Devolución

Movimiento que retorna un producto a su lugar de origen por una razón
justificada: producto vencido, dañado, incumplimiento de plazo, ya no
requerido, error al solicitarlo, o duplicidad. El producto retorna al
almacén de origen para ser **desechado** (→ stock de merma/dañado),
**auditado**, o **reintegrado** al stock disponible.

Toda devolución genera un reporte, dirigido a:

- **Área de almacén**: si la empresa devuelve a un proveedor, o una
  sucursal devuelve al almacén central.
- **Área comercial**: si un cliente devuelve un producto.

### Conteo y Ajuste

**Conteo**: verificación física de cuánto hay de un artículo inventariable
en un almacén. Puede ser de rutina (programado, periódico) o parte de un
proceso de ajuste/auditoría puntual. Si hay discrepancia entre lo contado
y lo registrado, genera un **Ajuste**.

**Ajuste**: acción de modificar el stock de un almacén para corregir esa
discrepancia. Se origina por sobrante, faltante, merma/daño, o error de
registro. Es válido (sin generar alarma) solo si está dentro de un margen
de error definido por las áreas de almacén y contabilidad; fuera de ese
margen dispara alarma/auditoría. Es un tipo de Movimiento (RN-GEN-001),
exige permiso y motivo (RN-INV-004), y quien lo solicita no es
necesariamente quien lo autoriza (RN-INV-006).

### Merma y Desperdicio

**Merma**: pérdida inevitable o imprevista de cantidad de un artículo
(procesamiento, limpieza, caducidad, pérdida natural de peso/líquidos en
perecederos, robo, vencimiento). Se reporta tanto en el módulo de
producción como en el de inventario — como parte del conteo en una
auditoría, o de alguna otra forma aún por definir. Debe estudiarse y
reportarse para tomar medidas correctivas; el estudio y la rendición de
cuentas son responsabilidad del almacén y el área contable. Es uno de los
motivos de Ajuste (`motivo_ajuste=merma`); `error_registro` queda aparte
porque no es una pérdida real.

**Desperdicio**: residuo de un proceso (cáscaras, espinas, huesos), a
diferencia de la merma potencialmente aprovechable. Se origina por el
diseño del proceso o por manipulación ineficiente. Se reporta en el
módulo de producción y puede asociarse a una receta como producto
derivado. Su aprovechamiento (si se diseña un proceso para ello) puede
impulsarse desde el área productiva, comercial o I+D+i.

Ejemplo (piña): Merma = parte oscura de la pulpa, no detectable al
comprar, no aprovechable. Desperdicio = cáscara y corazón — residuo del
proceso, potencialmente aprovechable.

El **stock de merma o dañado** es un subtipo de stock reservado: ya no
apto para la actividad económica, pendiente de auditoría y desecho. Se
genera por devolución, rechazo de un almacén de sucursal, o auditoría de
almacén (cruza con Merma/Desperdicio).

## Operación comercial

### Canal de Venta

Medio, ruta o plataforma que usa la empresa para hacer llegar sus
productos o servicios a los clientes: punto de venta en sucursal, kiosko,
central de pedidos, página web. Mantenimiento a cargo de la empresa;
promoción a cargo del área de marketing del grupo empresarial.

Cada canal aporta un porcentaje de los ingresos de la empresa; su
participación en los ingresos la mide y analiza el área comercial, para
decidir promocionarlo más, expandir su capacidad, o dirigir la estrategia.

- **Operado por humano** (trabajador): requiere capacitación y
  herramientas funcionales completas. Se evalúa: tiempo de atención,
  upsell, errores de digitación, encuestas de satisfacción del cliente.
- **Digital** (el cliente se atiende solo): se evalúa: conversiones,
  errores de sistema, cantidad de clics para completar el pedido,
  satisfacción del cliente, upsell de productos relacionados, ticket
  promedio.
- **Ambos**: tasa de registro/autenticación de clientes, y venta de
  productos promocionales o de lanzamiento.

### Modalidad de Consumo

Manera como un cliente recibe y disfruta los productos solicitados: mesa,
takeout, delivery. Determina la experiencia general, el tiempo de
permanencia, la ocupación y el nivel de autoservicio requerido.

Configurable por sucursal, marca o canal de venta — puede ofrecerse un mix
de las tres modalidades. Cada modalidad exige un número mínimo de datos
del cliente para aceptar el pedido (nombres, DNI, teléfono, dirección,
medio de pago a utilizar), variable según la modalidad. Los precios de
productos comerciales y servicios pueden variar entre una modalidad y
otra.

### Carrito

Espacio digital donde un cliente o usuario almacena y gestiona
temporalmente los productos comerciales seleccionados, mientras arma una
orden de pedido. Es el puente virtual entre la navegación y el envío de
la orden de pedido.

Reserva temporalmente el stock requerido por los productos seleccionados
(nuevo origen `carrito` de Stock Reservado — evita sobreventa). Si el
cliente desiste, el stock reservado vuelve a estar disponible.

Al enviarse el pedido:

- Si el punto de venta **admite** pedidos abiertos pendientes de pago: el
  pedido va a cocina (**KDS**, Kitchen Display System) y queda como
  "pedido abierto pendiente de pago".
- Si **no** admite pedidos abiertos: el carrito va primero a la pasarela
  de pago; al efectuarse el pago, el pedido va a KDS y se emite el
  comprobante de pago (boleta o factura).

### Medio de Pago

Forma como el cliente o la empresa realiza el pago por un bien o
servicio. Puede variar, aumentar, cobrar comisión a la empresa,
desaparecer, ser aceptado o rechazado. Algunos medios pueden activar
promociones. Si el medio es a crédito, la empresa puede aplicar una lista
de precios distinta a la del pago al contado.

- **Medios que la empresa acepta** (cobro): efectivo, tarjeta de
  crédito/débito, billeteras digitales (Yape), transferencia bancaria.
- **Medios que la empresa usa para pagar** (egreso): efectivo, tarjeta de
  débito, transferencia, cheques. También trabaja a crédito con otras
  empresas y regulariza el pago después — a cargo del área contable.

**Cadena de custodia del efectivo:**

1. El **cajero** es responsable de que los pagos estén conformes durante
   su turno.
2. Al cierre de caja, transfiere la responsabilidad al **encargado de
   tienda o supervisor**.
3. El **encargado/supervisor** recibe el dinero y lo pone a salvo, tras
   confirmar que los valores son correctos.
4. El **área contable** recibe el dinero, verifica los valores, toma
   responsabilidad, y lo pone a disposición de la empresa.

Los medios digitales dependen, para su mantenimiento y actualización, del
proveedor de servicios digitales y de la empresa de medios de pago
(conexiones seguras, aseguramiento de pagos). Ante disconformidad o
duplicidad de un cobro, el área contable envía una carta formal
detallando: operación, fecha, hora, cliente, referencia de pago, lote,
monto, y procedencia del pago (o su ausencia).

### Impuesto

Pago obligatorio que la empresa hace al Estado para financiar el gasto
público. Se calcula sobre ganancias, patrimonio, ventas y consumo.

- **Directos**: gravan directamente la generación de ingresos o ganancias
  netas de la empresa (ej. IR — Impuesto a la Renta).
- **Indirectos**: afectan la operación comercial (ej. IGV); lo paga el
  consumidor final.

Existen zonas económicas y regímenes tributarios que exoneran o reducen
impuestos. La empresa se ubica en la **región amazónica**, donde la Ley
de Promoción de la Inversión en la Amazonía (Ley 27037) exonera el IGV y
reduce la tasa de IR para el consumo/operación dentro de la región —
es el mismo beneficio normativo aplicado a dos tributos. Compras y pagos
a proveedores **fuera** de la región amazónica sí están afectos a IGV;
por eso el IGV es **configurable por proveedor** (dentro/fuera de zona).

Otros tributos relevantes para la operación:

- **SPOT (Sistema de Detracciones)**: retiene un porcentaje en compras de
  ciertos insumos o servicios, depositado en el Banco de la Nación;
  configurable por artículo/proveedor.
- **Impuesto Predial y Arbitrios municipales**: pago anual solo aplicable
  a sucursales con tenencia `propia`.
- **ITAN (Impuesto Temporal a los Activos Netos)**: grava el excedente de
  activos netos de la empresa por encima del umbral legal; es un crédito
  aplicable contra el IR.

El pago y la configuración de impuestos son responsabilidad del área
contable o de asesores contables externos; parte de su responsabilidad es
asesorar a la empresa para minimizar el pago de impuestos y maximizar su
inversión.

### Precio

Cantidad de dinero que se cobra y se paga por un producto o servicio.
Debe generar beneficio económico: no debe superar el valor percibido por
el consumidor, ni estar por debajo del costo. Es estudiado por las áreas
comercial, contable e I+D+i.

Es mutable, tiene variaciones, y se puede negociar dentro de un rango
establecido por el área comercial (ej. en cotizaciones). En los puntos de
venta de sucursal, kiosko y web, los precios son **fijos e innegociables**
— solo varían según ofertas, descuentos o condiciones establecidas por la
marca o el grupo empresarial, aplicadas vía lista de precios.

Se expresa en una sola divisa: la moneda oficial del país.

### Lista de Precios

Mecanismo para manejar los precios de los productos comerciales de la
empresa: segmenta por tipo de consumidor, identifica productos
promocionales, y define precios mínimos y máximos. La crea el área
comercial, con asesoría del área contable. Disponible en el ERP.

### Promoción

Estrategia de marketing orientada a promocionar o dar a conocer uno o
varios productos. Incluye comunicación, material promocional,
capacitación del personal, y un tiempo de duración definido. La
determinan las áreas comercial, marketing y contabilidad.

Vive en los canales de venta y en el ERP; se adecua a horarios y fechas.
Debe estar dentro del guion de atención del personal de atención al
cliente. Se liga a una Lista de Precios (`es_promocional`).

Objetivos: lanzamiento, fidelización, rotación de inventarios, o aumentar
el ticket promedio.

### Programa de Puntos

Acción de marketing y comercial que busca fidelizar al cliente a la marca
y a las demás marcas del Grupo Empresarial. Los puntos se acumulan según
el producto consumido y se almacenan en la cuenta del cliente; el cliente
puede usarlos en cualquier canal de venta y en cualquiera de las marcas
del grupo (descuentos a lo largo de todas las marcas de Majambo). Tienen
vigencia.

El valor de los puntos se ajusta según el producto comercial o el monto
consumido; lo determinan las áreas comercial y de marketing.

Implicación de modelo: el **Cliente es una entidad a nivel de Grupo
Empresarial**, no de una empresa o marca individual — es la excepción
explícita a que toda acción ocurra en un solo contexto de tenant
(RN-GEN-003), ya que el cliente y sus puntos deben reconocerse en
cualquier empresa/marca del grupo.

## Información

### Dato

Unidad de información sin procesar, recolectada en el ERP o de manera
física, usada para eliminar suposiciones. Puede ser números, hechos,
nombres, medidas, precios, costos, etc.

Al ordenarse, catalogarse y analizarse, se convierte en **Información**
— usada para tomar decisiones estratégicas, mejora continua, anticipar
tendencias, conocer al cliente, y hacer predicciones.

Se almacena por tiempo indefinido. En el ERP vive en bases de datos bien
estructuradas que facilitan su lectura y procesamiento; no puede
duplicarse ni omitirse; debe tener estructura y tipo homogéneo según su
naturaleza.

Responsabilidades: rellenar el dato es responsabilidad del trabajador;
analizarlo, del área correspondiente; su disponibilidad, del ERP.

### Registro

Dos acepciones:

1. **Huella/evidencia**: documento físico o digital que evidencia una
   actividad, transacción, acto legal o movimiento de la empresa. Es el
   término más genérico — Documento y Movimiento (ya definidos con más
   detalle) son casos concretos de Registro, junto con cualquier otra
   huella (`audit_log`, asiento contable).
2. **Acción**: ingreso de datos al sistema — dar de alta un cliente,
   producto, proveedor, etc.

### Historial

Registro detallado y ordenado de eventos, antecedentes y acciones pasadas
de algo o alguien. Su objetivo es que la información pasada pueda
encontrarse con facilidad, y permitir análisis históricos.

Todo historial debe poder verse en el ERP; debe ser sencillo ordenarlo,
filtrarlo, y acotarlo por rango de fechas. Solo lo consulta personal con
acceso autorizado.

Ejemplos: historial de ventas (por cliente, canal, fecha, usuario),
historial de compras (por producto, proveedor, categoría), historial de
movimientos de SKU por almacén.

### Archivo

Conjunto de datos o información estructurada que se almacena de manera
física o digital. El ERP puede generar archivos diversos (documentos);
también admite archivos subidos: Excel, CSV, Word, presentación, TXT,
PDF, PNG, JPG, MP4, MOV (distintos códecs de video).

El ERP tiene directorios de carpetas y archivos que pueden vincularse a
diferentes entidades de su base de datos. Ejemplos: un video ligado a un
reclamo de cliente, una foto ligada a evidencia de un producto dañado
desde almacén, un documento Word generado con el reporte detallado de una
auditoría.

Se origina de dos formas: generado automáticamente por el ERP (con datos
y plantillas existentes), o subido por el usuario según amerite el caso.

### Evidencia

Conjunto de información y datos observables y verificables que demuestran
o refutan una hipótesis o reclamo. Su objetivo es dar claridad respecto a
los hechos.

Recopilarla y proveerla al ERP es responsabilidad del trabajador
encargado de sustentar el hecho que va a reportar o elevar a la siguiente
instancia. El cliente también puede enviar a la central fotos, videos o
audio que sustenten su reclamo; el personal debe subirlos al ERP.

Termina dentro de un Reporte, para darle sustento (usa Archivo como
soporte); se analiza por las áreas correspondientes según lo que el
reporte demande.

## Actores

Taxonomía de personas y entidades con contacto con la empresa, por tipo
de vínculo. Terminología oficial en
[glossary.md](../foundation/glossary.md#actores).

### A. Trabajan EN la empresa (vínculo laboral)

- **Trabajador** (base): persona con vínculo laboral (D.S. 003-97-TR:
  prestación personal + remuneración + subordinación).
- **Practicante / Pasante**: modalidad formativa laboral (Ley 28518, D.S.
  007-2005-TR) — NO genera vínculo laboral. Jornada máxima 6h/día, 30h/
  semana. Subvención mínima = 1 RMV si cumple jornada máxima. Derecho a
  EsSalud o seguro equivalente (mín. 14 subsidios por enfermedad, 30 por
  accidente). Sin CTS, gratificaciones ni indemnización por despido.
  Tipos: práctica preprofesional (aún estudiante, sin tope legal fijo —
  depende del plan curricular) o práctica profesional (ya egresado, tope
  12 meses salvo ampliación del centro de formación). *Pendiente de
  verificar en el reglamento: % máximo de practicantes según tamaño de
  planilla de la empresa.*
- **Personal por locación de servicios (RHE, 4ta categoría)**: presta
  servicio sin subordinación (Código Civil), emite Recibo por Honorarios.
  ⚠ Riesgo legal activo: SUNAFIL (Res. Sala Plena 014-2024 y
  004-2025-SUNAFIL/TFL) declara vínculo laboral retroactivo —con CTS,
  gratificaciones, vacaciones y EsSalud— si en los hechos hay horario
  fijo, control de asistencia o subordinación, aunque el contrato diga
  "locación de servicios". **El ERP no debe registrar horario/asistencia
  de un locador** — es evidencia de subordinación.
- **Gerencia / Directivo**: trabajador con facultades de representación y
  decisión delegadas (autoriza contratos, gastos, sanciones — RN-CTR-003,
  RN-EMP-*). Es un `trabajador` con facultades, no entidad aparte.

### B. Trabajan CON la empresa (terceros, sin vínculo laboral)

- **Proveedor**: ya modelado (compras).
- **Transportista/repartidor propio**: ya modelado (`vehiculo.responsable_id`,
  vínculo laboral).
- **Repartidor de plataforma externa**: entrega pedidos vía una plataforma
  externa (Rappi, Uber Eats, PedidosYa) — sin vínculo laboral ni control
  operativo de la empresa. ⚠ Estado legal (Perú, a la fecha): NO hay ley
  vigente que regule riders de plataformas; hay +20 proyectos de ley desde
  2016, ninguno aprobado — no exigible, no vigente. La empresa no lo
  gestiona como recurso propio (no aplica Vehículo/Mantenimiento).
- **Consultor / Asesor externo**: asesora (legal, contable, marketing) por
  locación de servicios u OC de servicios; mismo riesgo de subordinación
  que el personal por locación de servicios si se le exige horario.
- **Contratista de mantenimiento/servicio técnico**: caso de `proveedor`
  tipo servicio, ya referenciado en `orden_mantenimiento.proveedor_servicio_id`.
- **Empresa licenciataria** (franquicia interna): ya modelada
  (`licencia_marca`).

### C. Trabajan PARA la empresa, fuera de su estructura

- **Socios / Directorio del Grupo**: dueños del Grupo Empresarial; ya
  referenciados en reglas (RN-GRP-006 aprobación unánime, RN-MAR-004
  modificación de marca). No son `trabajador` ni `usuario` necesariamente.
- **Auditor externo**: ya modelado (`auditoria.entidad_auditora`).
- **Entidad regulatoria**: SUNAT, SUNAFIL, DIGESA, municipalidad. No
  interactúa con el ERP directamente; genera obligaciones ya modeladas
  (PLAME, licencias, predial).
- **Entidad financiera**: banco, pasarela de pago (Izipay). Ya
  referenciada (`pago.pasarela`, custodia de efectivo → contabilidad).

### D. Clientes / consumidores

- **Cliente final**: ya modelado (`cliente`, transversal al grupo).
- **Cliente corporativo**: persona jurídica que compra (ej. catering,
  eventos). Caso de uso de `cliente` (razon_social+ruc), no entidad
  aparte.
- **Cliente con Programa de Puntos**: ya modelado (`cuenta_puntos`).
- **Cliente anónimo**: compra sin registrar datos (ej. boleta simple);
  `cliente_id` ya es opcional en `venta` — es un caso válido, no un error
  de captura.

### E. No transaccionales

- **Comunidad / vecindario**: relevante para permisos municipales, quejas
  de ruido/olores; sin entidad propia en el ERP — se gestiona vía
  reclamos/actas si aplica.
- **Postulante**: candidato en proceso de selección, aún no contratado.
  Rige Ley 29733 (Protección de Datos Personales) + reglamento D.S.
  016-2024-JUS: exige consentimiento previo, informado y expreso para
  tratar y conservar sus datos (CV). ⚠ No hay plazo legal fijo en Perú
  para retener datos de un postulante no contratado (a diferencia del
  RGPD europeo) — la obligación real es declarar el plazo en el aviso de
  privacidad y respetar derechos ARCO (acceso, rectificación, cancelación,
  oposición) en cualquier momento.

## Auditoría

Proceso de evaluación sistemática y objetiva de un proceso, registro o
estado dentro de la empresa. Analiza la exactitud de los registros, la
eficiencia de los procesos, los controles internos, y el cumplimiento de
normativas, políticas y procesos.

- **Interna**: la realiza la propia empresa; a cargo de distintas áreas
  según dónde se detecte el problema, o como parte de una rutina de
  supervisión o mejora continua.
- **Externa**: la realiza el grupo empresarial (políticas de cumplimiento
  o gobernanza), o una empresa consultora externa, para obtener
  información imparcial y objetiva.

Se dispara por: reportes de alarma ante inconsistencias de inventario,
alertas de malas prácticas, reclamos, o sanciones aplicadas por entidades
regulatorias. Es un proceso, no un tipo de Movimiento.

## Documentos de negocio

Un **Documento** es un testimonio material (físico o digital) que registra
información útil y ordenada; soporte administrativo, legal e informativo.
Ayuda a entender un evento, tomar decisiones, y estructurar información
extraída de los datos.

El ERP y la empresa deben poder generar documentos de forma manual o
automática; todo proceso de la empresa debe incluir, entre sus pasos, la
creación de documentos cuando haya información útil que registrar; y
ambos deben archivarlos y revisarlos.

Todo documento tiene: fecha de elaboración, un responsable que lo visa, un
propósito, una fecha de entrega pactada, y debe ser veraz. Una vez emitido
es inmutable — corrección vía documento inverso o anulación auditada
(RN-GEN-002).

Ejemplos: inventarios, comprobantes de pago, planillas, reportes,
contratos, informes de eventos, y los ya definidos en el ERP (Orden de
Compra, Venta, Comprobante, Asiento contable, Guía de Remisión, Solicitud,
Transferencia).

### Solicitud

Petición mediante la cual una empresa, cliente, trabajador o entidad pide
un producto, servicio, beneficio, documento o información a la empresa, a
un área, a un punto de venta, o a un trabajador. Comunica una necesidad de
forma clara; es un tipo de Documento. Registra: fecha de ingreso,
destinatario, emisor, detalle/cuerpo (lo solicitado), lugar de origen.

Sujeta a aprobación o rechazo. Ejemplos: solicitud de trabajador para un
permiso de día libre; solicitud de la empresa a una institución del
estado para una licencia; solicitud de insumos de una sucursal al almacén
central (`solicitud_insumos`, ya modelada — caso concreto de este
concepto marco, ámbito inventario).

### Orden

Documento instructivo y mandatorio: su ejecución es obligatoria.
Unidireccional — va de un ente superior hacia uno subordinado (a
diferencia de la Solicitud, que admite aprobación o rechazo). Registra,
como todo Documento: emisor, destinatario, fecha, cuerpo detallado,
ubicación, fecha de entrega.

Tipos: Orden de Pedido (el pedido del cliente, ya confirmado en el punto
de venta — reclasificado desde Solicitud, porque una vez confirmado es de
ejecución obligatoria; "Pedido" es solo su nombre coloquial, ej. "dónde
está el pedido de la sucursal X"), Orden de Compra, Orden de Pago, Orden
de Servicio, Orden de Trabajo.

### Cotización

Documento comercial informativo formal mediante el cual un proveedor o la
empresa detalla el precio exacto de un producto o servicio. No obliga al
solicitante a comprar — solo informa costos. Registra: datos de la
empresa emisora y receptora, descripción del producto/servicio, precios
unitarios y totales, condiciones de pago, impuestos, medios de pago
aceptados, vigencia de la oferta.

Requerida para evaluar una compra; algunos proveedores exigen cotización
antes de vender (precios sustanciales, sujetos a variación/condiciones).

- **Recibida de un proveedor**: la solicita el área de compras; la evalúa
  contabilidad y finanzas.
- **Emitida por la empresa** (a pedido de un cliente): la emite el área
  comercial, según tarifario, lista de precios y rango de negociación
  admitido por la empresa.

### Reporte de Producción

Documento generado al finalizar una jornada de producción en cocina de
producción; consolida todos los datos de la jornada: insumos utilizados
por receta, solicitudes de producción cubiertas y pendientes,
observaciones, lotes producidos, merma, desperdicios. Debe ser visado por
el encargado o jefe de cocina responsable. Se genera automáticamente en
el ERP con los datos que los usuarios fueron llenando durante la jornada.
Mide la eficiencia de la cocina de producción, el cumplimiento, y los
puntos de mejora.

### Comprobante de Pago

Documento que certifica que un cliente o la empresa ha recibido un
producto o servicio; respalda los ingresos de la empresa (venta) o los
egresos de esta (compra a proveedor). Registra: productos/servicios
entregados o recibidos, cantidades, precios unitarios y totales,
impuestos aplicados, fecha, datos del emisor, datos del receptor.

- **Emitidos por la empresa**: solo boleta y factura.
- **Aceptados por la empresa** (como compradora): factura, RHE, y
  excepcionalmente boleta o ticket de compra.

Se sustenta con: ingreso en efectivo, voucher de pago del proveedor de
medios de pago, movimientos bancarios, o un contrato que autoriza un
crédito. No puede realizarse una venta sin la emisión de un comprobante
de pago; se emite desde un punto de venta o desde el área comercial.
Todos los comprobantes son recepcionados y procesados por contabilidad.
Los pagos a proveedores los realiza contabilidad, según lo pactado en el
contrato o lo solicitado según la cotización.

El número de serie se asigna por punto de venta, con correlativo propio;
cada empresa tiene sus propios comprobantes (serie/correlativo no se
comparten entre empresas del grupo) y no puede repetir uno emitido dentro
de sí misma. El ERP o el proveedor de facturación (Factiliza) debe
garantizar un mecanismo anti-duplicado y anti-reemisión.

### Guía de Remisión

Documento formal regulado que certifica que la mercancía transportada es
legal y de buena fe. La empresa la emite de forma interna para traslados
entre almacenes. Contiene: fecha de inicio del traslado, lista de bienes
transportados y sus cantidades, RUC del emisor y del receptor, lugar de
origen y destino, motivo del traslado, datos del transporte (chofer,
vehículo).

La emite el área de almacén. Todas se almacenan y resguardan en el área
de contabilidad. Todo se gestiona en el ERP.

### Contrato

Documento escrito que suscribe un acuerdo legal entre dos partes; obliga
a ambas a cumplir una serie de condiciones. Su función: crear, regular,
modificar o extinguir una relación jurídica. Requiere consentimiento de
ambas partes, un objeto sobre el cual trata, y un motivo lícito.

Ejemplos: contrato laboral, de alquiler, de prestación de servicios,
comercial.

Todo contrato emitido por la empresa usa una plantilla; debe ser visado
por un abogado; se actualiza según los reglamentos y leyes del país.
Distintas áreas pueden suscribirlo según sus facultades y necesidades,
autorizadas por gerencia. Todo contrato se registra en el ERP.

### Documentos de recursos humanos

El módulo RRHH tiene su propia familia de documentos, ligados al
**trabajador** (vínculo laboral de una persona). Los datos personales
(nombres, documento, domicilio) no viven en `trabajador` sino en una
entidad única **`persona`** (party model, RN-GEN-007), que también usan
`cliente` y `usuario`; así ningún nombre se duplica. Un `trabajador` es
distinto de un `usuario` (identidad de login): pueden existir por
separado. En los documentos, los roles (emisor, destinatario,
representante, aprobador) se resuelven a una persona vía su trabajador. Todos pertenecen a una empresa y se rigen por
la legislación laboral peruana vigente; las cartas y actas usan plantillas
versionadas (ver `docs/templates/rrhh/`), visadas por abogado antes de uso.

- **Boleta de pago (planilla)**: comprobante mensual de remuneración y
  descuentos (ONP/AFP, renta de 5ta, adelantos, faltas) y aportes del
  empleador (EsSalud). Refleja la planilla electrónica (PLAME); se entrega
  a más tardar el 3.er día hábil del mes siguiente (D.S. 001-98-TR).
- **Certificado de trabajo**: al cese, dentro de 48 horas, indica tiempo
  de servicios y cargo(s); a solicitud del trabajador puede incluir
  conducta y desempeño (art. 45, D.S. 001-96-TR).
- **Liquidación de beneficios sociales**: al cese; CTS pendiente,
  vacaciones truncas, gratificación trunca y otros adeudos; se paga dentro
  de 48 horas del cese.
- **Memorándum**: comunicación interna formal, jerárquica y unidireccional
  (instrucción, recordatorio, felicitación, observación). No es una
  sanción por sí mismo.
- **Carta de amonestación**: sanción disciplinaria escrita, dentro del
  poder de dirección del empleador (art. 9, LPCL D.S. 003-97-TR). Respeta
  proporcionalidad, inmediatez, razonabilidad y non bis in idem; da
  derecho al descargo del trabajador; es escalón previo a suspensión o
  despido.
- **Acta**: deja constancia formal de un hecho (reunión, incidente,
  entrega de cargo, arqueo, verificación); firmada por los presentes.
- **Solicitud de permiso / licencia / vacaciones**: pedido del trabajador
  para ausentarse — vacaciones (30 días/año, D.Leg. 713), licencia con o
  sin goce de haber, permiso por horas; sujeto a aprobación. Es un caso
  concreto del concepto marco Solicitud.
- **Pacto de permanencia por capacitación**: acuerdo por el cual, a cambio
  de que la empresa financie un curso, posgrado, diplomado o capacitación,
  el trabajador se compromete a permanecer un plazo determinado; si se
  retira antes, reembolsa proporcionalmente lo invertido. Debe ser
  razonable y proporcional (plazo y monto) para no vulnerar la libertad de
  trabajo. Es un tipo de Contrato.
- **Registro de asistencia**: control de marcaciones (entrada/salida),
  base de tardanzas y horas extra (registro de control de asistencia
  obligatorio, D.S. 004-2006-TR).
- **PLAME / T-Registro**: planilla electrónica ante SUNAT — T-Registro
  (datos de empleador y trabajadores) y PLAME (remuneraciones mensuales).

> Nota legal: las definiciones y plantillas de RRHH son una base
> profesional, no asesoría legal; deben ser visadas por un abogado y
> adaptadas a la norma vigente al momento de usarse.

### Compra, Venta y Transferencia no son Documento

Son **operaciones económicas** (procesos con estado, no testimonios
materiales); cada una genera el Documento que le corresponde: Compra →
Orden de Compra (+ Guía de Remisión al recibir); Venta → Comprobante de
Pago; Transferencia → Guía de Remisión.

- **Compra**: puede originarse en una cotización de proveedor — al
  recibir respuesta, el borrador de la OC se actualiza con los precios
  unitarios cotizados. Toda compra se sustenta con un comprobante de
  pago, exige un egreso de dinero o un crédito con plazo determinado, y
  genera asientos contables y un movimiento de dinero.
- **Venta**: si es de un servicio, o generada por el área comercial,
  puede originarse en una cotización que el cliente acepta. Flujo: orden
  → preparación de pedido → listo → entrega → pago → emisión de
  comprobante → entregado → devolución (si aplica). El pago puede ser
  adelantado; el comprobante puede emitirse antes del pago (no
  recomendable).
- **Transferencia**: ya modelada (ver Almacenes/Guía de Remisión).

## Almacenes

- **Central**: recibe SKUs de proveedores, personal de compras y de la
  cocina de producción (productos preparados); despacha a los almacenes de
  sucursal y a la cocina de producción. Custodia insumos, empaque, menaje,
  utensilios, productos de limpieza, equipamiento no entregado, mercadería,
  merchandising, uniformes. Usa FEFO/FIFO; conteos periódicos por categoría
  de insumo; auditorías inopinadas (grupo empresarial o empresa operadora).
  Equipamiento obligatorio: balanza industrial, balanza digital, lectora de
  código de barras, impresora de etiquetas, anaqueles, área de fríos, área
  de congelados, zona de carga y descarga; conexión al ERP; autorización y
  seguridad contra incendios/robos vigentes.
- **Producción**: almacén transitorio dentro de una cocina de producción;
  guarda insumos para producir, recetas en elaboración y productos
  terminados enfriando/empacados. Solo despacha al almacén central (nunca
  directo a sucursal).
- **De sucursal** (sub-almacén): integra todo el stock de una sucursal. Su
  stock mínimo/máximo por SKU depende del tamaño y rotación de la sucursal;
  no puede exceder el máximo ni caer bajo el mínimo para la jornada
  siguiente. Se abastece del almacén central de su empresa; puede recibir
  traspaso de urgencia desde el sub-almacén de otra sucursal (cualquier
  marca/empresa — si es entre empresas, se subsana con factura de venta en
  el cierre de mes). Usa FEFO/FIFO; conteos periódicos generan la solicitud
  de requerimiento a almacén central. Control a cargo del encargado de
  tienda (o supervisor designado). Productos dañados/vencidos se etiquetan
  "NO USAR" y se separan de los productos buenos.

## Almacenes no físicos (virtuales)

- **De Transporte**: hoy no es ubicación física; es el estado `en_transito`
  de una transferencia (stock descontado de origen, aún no ingresado a
  destino). Ver [state-machines.md](state-machines.md#transferencia). Si la
  operación crece, puede evolucionar a un nodo físico real (hub de
  tránsito: stock ya pickeado y embalado esperando cargarse a un
  vehículo) — el modelo de almacenes (`almacen.tipo`) debe ser extensible
  para soportar este y otros nodos futuros sin romper el diseño existente.
- **Virtual de Activos**: no es ubicación física; registro a nivel empresa
  de activos existentes, nuevos y dados de baja. Solo permite salida
  (venta/baja) de un activo depreciado en su totalidad, con acta de
  autorización. La depreciación la controla el área contable de la empresa
  (visible a nivel ERP, no es responsabilidad del almacén). Desde el módulo
  de almacén, al seleccionar el activo, se visualizan ficha técnica, número
  de serie, fecha de compra, proveedor, número de factura, depreciación e
  historial de mantenimiento/reparaciones — datos que no carga el almacén.

## Cocina de Producción

Espacio físico donde se producen subrecetas y se mantiene el estándar de
sabor/calidad de los productos resultantes; contiene su propio almacén de
tipo `produccion`. Sigue cronograma por tipo de receta/proceso (evita
contaminación cruzada) y homologación con el resto de cocinas del grupo.
Detalle completo en [../foundation/vision.md](../foundation/vision.md#cocina-de-producción)
y reglas en [business-rules.md](business-rules.md#cocina-de-producción).
Estado actual: no existen cocinas de producción (planeada la primera en
2027); toda la producción se hace en sucursales.

## Módulos del dominio (visión completa)

Ventas, Clientes, Productos, Inventario, Compras, Caja, Contabilidad, RRHH,
Producción, CRM, Tesorería, Activos, Proyectos, BI, Reportes, Transporte,
Supervisión. Estado e índice en [../product/modules.md](../product/modules.md).
