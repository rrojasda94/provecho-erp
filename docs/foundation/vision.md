# Visión y modelo de negocio

## Visión

Un solo sistema que opere todo el grupo gastronómico — de la compra del insumo
a la venta del plato y su asiento contable — 100% modular: cada capacidad se
agrega o quita sin romper el resto.

## Organización

```
Grupo Empresarial
├── Almacén Central (ingredientes, empaques, bebidas, insumos)
├── Marca A (Charlie's)   → Local 1, Local 2
├── Marca B (Ariana)      → Local 1
├── Marca C (La Avenida)  → Local 1
└── Marca D (...)
```

Niveles: **Grupo → Empresa → Marca → Sucursal → Almacén de sucursal**.
Todos los restaurantes pertenecen a la misma empresa. El almacén central
abastece a los locales; algunos insumos se fabrican (producción).

### Grupo Empresarial Majambo

Conjunto de sociedades legalmente independientes, unificadas bajo una misma
dirección y control económico, propiedad de un grupo familiar (dirección
delegable a terceros con capacidad). Objetivo: operar como una sola unidad
estratégica para ganar competitividad, diversificar riesgos y optimizar
recursos entre las empresas miembro.

Su núcleo es el rubro gastronómico, pero puede abarcar empresas de logística,
transporte y servicios varios orientadas a las necesidades del grupo. Estas
empresas de soporte pueden además atender terceros, siempre sin exponer la
inteligencia interna (know-how, procesos, datos) de las empresas del grupo.

Responsabilidades del Grupo: alinear objetivos corporativos, asignar recursos
de capital, direccionar el crecimiento, definir estrategia unificada, asegurar
cumplimiento legal y fiscal, estandarizar gobierno corporativo, proteger
propiedad intelectual, centralizar compras/proveedores, garantizar
financiamiento y evitar conflictos de interés.

### Empresa

Organización de personas y recursos para producir bienes o servicios; unidad
legal (RUC) perteneciente al Grupo Empresarial, que separa y organiza recursos
para cumplir los objetivos del grupo sin comprometer su propia rentabilidad.

Tipos: operativa, logística, prestadora de servicios, de asesoría,
transporte (ampliables por configuración).

Responsabilidades: ejecutar su actividad económica, pagar sus propias
cuentas, cumplir lineamientos y objetivos del Grupo, mantener su propia
rentabilidad, solicitar préstamos solo con estudio de viabilidad previo del
área contable (evalúa monto, motivo, tasas y plazos), y cumplir la
legislación tributaria y legal del área donde opera.

Puede prestar servicios y ejecutar actividades a clientes/empresas fuera del
grupo, y contratar servicios/sistemas/soporte de terceros externos siempre
que no afecte la rentabilidad del grupo ni la propia.

Configurable en el ERP: RUC, domicilio fiscal, contacto, sucursales, marcas,
planilla, organigrama, políticas internas, horarios, roles, rango de sueldos.

Empresas actuales del grupo:

1. **Inversiones Turísticas y Alimentarias Majambo EIRL** (RUC 20450311520) —
   empresa operadora, dueña de los activos.
2. **Servicios Rentaurant** (RUC 20610077782) — nombre compuesto de RENTar
   equipos para RestauranTes; actualmente de baja de oficio, próxima
   reactivación para adquirir activos y prestar servicio de alquiler de
   equipos.

### Marca

Enseña comercial e identidad bajo la cual se vende un producto/servicio al
público. Sus derechos de identidad pertenecen al holding (Grupo Empresarial);
las empresas del grupo obtienen licencia para operar una o más marcas, como
una franquicia interna. La marca no posee activos tangibles — esos los posee
la empresa que la opera.

No limitada a restaurantes: puede ser marca de restaurante, delivery,
servicio de limpieza, almacén en frío, etc. (ampliable por configuración).

Responsabilidades: definir su identidad (skins de marca para la TPV), su
carta/menú de productos comerciales y/o catálogo de servicios, sus procesos
operativos y protocolos de contratación, sus propias recetas, licenciar su
uso a una o más empresas del grupo, e impulsar innovación/rebranding.

Relaciones: opera en una o más sucursales; vende sus propios productos y/o
presta servicios; puede vender mercadería complementaria si el rubro lo
amerita (ej. gaseosas, merchandising); toda empresa licenciataria debe seguir
sus procesos, recetas y protocolos; solo puede ser modificada por la empresa
dueña del holding, a través del área de manejo de marca.

Configurable en el ERP: skins de la marca para la TPV, carta/menú, procesos
operativos y protocolos de contratación, recetas de la marca, empresas
licenciatarias y sucursales asignadas, política de innovación/rebranding.

Marcas actuales: **Charlie's Pizzas** (activa). Próximas a crear:
**Pastivoro**, **La Avenida**, **Bur Bur**, **Ariana**.

### Sucursal

Espacio físico donde una empresa opera una marca (solo una a la vez). Cuenta
con su propio almacén de sucursal para SKUs/productos inventariables, y se
abastece del almacén central — salvo excepciones puntuales (gas, bebidas
embotelladas) entregadas directo por proveedor, cuya autorización y pago
gestiona el área correspondiente, no la sucursal.

Tenencia: propia de la empresa, alquilada a un tercero ajeno, o propiedad
del grupo empresarial.

Responsabilidades: operar la marca asignada; custodiar su almacén; mantener
personal designado por la empresa vía ERP bajo un horario laboral definido;
mantener bienes muebles, material de marca y equipamiento según los manuales
comerciales de la marca; mantener vigentes autorizaciones municipales y
regulatorias; mantener dispositivos de seguridad; recibir mantenimiento y
mantener instalaciones impecables; mantener al día los pagos de
funcionamiento (los ejecuta la empresa responsable); seguir lineamientos y
estándares de calidad de la marca y del grupo; proveer bioseguridad a
personal fiscalizador; ejecutar traspasos de urgencia de insumos a otras
sucursales vía ERP, bajo condiciones de seguridad que garanticen el buen
estado del SKU transportado.

Restricciones: el personal de sucursal no puede comprar ni pagar a
proveedores sin autorización expresa de la empresa operadora; tiene áreas
restringidas a personal no autorizado; la apertura/cierre de una sucursal
requiere estudio de mercado y viabilidad hecho por la holding o una
consultora autorizada por esta.

Ciclo de vida: puede cambiar de marca, cambiar de dueño/inquilino, o darse
de baja.

### Cocina de Producción

Espacio físico donde se producen subrecetas y se empaquetan para su envío al
almacén central. Guarda las recetas y define la calidad de las bases que
tendrán los productos comerciales una vez preparados en las cocinas de
sucursal. Cuenta con un almacén transitorio propio (insumos, recetas en
elaboración, productos terminados enfriando o empacados).

Objetivo: centralizar la producción de subrecetas, manteniendo el estándar
de sabor y calidad de los productos resultantes, bajo control riguroso de
higiene e inocuidad, homologado en todas las cocinas de producción del
grupo.

Responsabilidades: producir subrecetas según receta definida; empaquetar y
etiquetar productos terminados; enviar productos terminados/subrecetas al
almacén central (nunca directo a sucursal); seguir un cronograma de
producción por tipo de receta/proceso evitando contaminación cruzada;
controlar con rigor tiempos, temperaturas, envasado y etiquetado; controlar
temperatura y humedad ambiente; desinfectar y secar alimentos frescos y
usarlos casi inmediatamente; solicitar insumos al almacén central vía ERP
viendo niveles de inventario y programando según demanda predictiva; enviar
guía de remisión al almacén central al devolver SKUs sobrantes al finalizar
el trabajo; dar mantenimiento regular a equipos sin interferir con la
producción; capacitar constantemente al personal en bioseguridad,
trazabilidad, inocuidad y manipulación alimentaria.

Restricciones: no entrega a almacenes de sucursal directamente; no puede
ingresar personal no autorizado ni sin elementos de bioseguridad; no puede
haber restos de comida sobrante en ninguna superficie ni equipo; ante
posible plaga/invasión de animales debe detener operación, solicitar
eliminación a la empresa operadora y luego desinfección total antes de
reanudar; debe estar homologada con todas las cocinas de producción del
grupo.

Configurable en el ERP: horario laboral, cronograma de producción por
tipo de receta/proceso, equipamiento completo y calibrado (balanzas,
medidores de pH, viscosidad, salinidad, azúcar, alcohol, etc.), plan de
mantenimiento rutinario de equipos, control de temperatura/humedad
ambiente, programa de capacitación (bioseguridad, trazabilidad, inocuidad,
manipulación alimentaria).

Estado actual: no existen cocinas de producción — toda la producción se
hace en sucursales. Primera cocina de producción planeada para 2027.

## Geografía y punto de venta

### Región

Agrupador geográfico de ciudades que presentan características
geográficas, culturales o climáticas similares. Puede ser tan grande como
un país o tan pequeña como una ciudad, siempre que cumpla esas
características.

Objetivo: servir de unidad de análisis estratégico para decidir la
expansión del grupo hacia nuevos mercados.

Responsabilidades: agrupar ciudades con características similares; servir
de base para el análisis de viabilidad y estrategia de ingreso a nuevos
mercados.

Relaciones: agrupa una o más ciudades; su viabilidad y estrategia de
ingreso las analizan en conjunto las áreas de marketing, finanzas,
operaciones y comercial del grupo empresarial.

Restricciones: no se ingresa a una nueva región sin el análisis de
viabilidad y estrategia de las áreas correspondientes.

Configurable en el ERP: nombre, características que la definen (geográficas,
culturales, climáticas), ciudades agrupadas.

### Ciudad

Unidad geográfica urbana con densidad poblacional alta, movimiento
económico, conectividad, servicios básicos y un mercado dinámico. Se
identifica por un nombre.

Objetivo: servir de unidad de análisis para decidir el ingreso del grupo a
un nuevo mercado urbano, y de marco para ubicar sucursales dentro de ella.

Responsabilidades: agrupar zonas o áreas de servicio; servir de base para
el análisis de mercado antes de ingresar; servir de marco para encontrar
ubicación de sucursal, encontrar proveedores, y determinar qué marca(s)
tienen más sentido para el público objetivo determinado.

Relaciones: pertenece a una región; tiene una o más zonas/áreas de
servicio; alberga sucursales.

Restricciones: no se ingresa a una nueva ciudad sin investigación de
mercado (igual que región).

Configurable en el ERP: nombre, región a la que pertenece, zonas/áreas de
servicio.

### Zona / Área de Servicio

Espacio dentro de una ciudad en el que esta se subdivide. La división puede
adaptarse a los barrios o distritos existentes, o a divisiones propias
determinadas por la capacidad de atención de una marca, sucursal o empresa.

Objetivo: delimitar el alcance real de atención de cada sucursal dentro de
una ciudad, según su capacidad.

Tipos: **servicio regular** (se atiende sin restricciones durante el
horario de atención), **servicio limitada** (restricciones horarias o
climáticas), **servicio restringida** (no se atiende, por seguridad o
imposibilidad), **fuera de área de servicio** (zonas alejadas del radio de
atención de la(s) sucursal(es)).

Responsabilidades: delimitar el alcance de atención de una o más
sucursales; clasificarse en uno de los cuatro tipos.

Relaciones: pertenece a una ciudad; cada sucursal se suscribe a un grupo de
áreas de servicio; la empresa decide cuáles áreas son limitadas y cuáles
restringidas.

Restricciones: un área restringida no se atiende; un área limitada solo se
atiende dentro de sus restricciones horarias/climáticas; un área fuera de
servicio no se atiende.

Configurable en el ERP: tipo, sucursales suscritas, restricciones
horarias/climáticas (si es limitada), motivo de restricción (si es
restringida), geocerca (polígono geográfico, trazada por la empresa).

### Punto de Venta (POS)

Lugar virtual asociado a una sucursal, interconectado en el ERP con
inventarios, productos comerciales, medios de pago, clientes, listas de
precio y emisión de comprobantes. Permite a los trabajadores atender a los
clientes con sus órdenes de compra.

Canales: **POS de trabajador** (hardware en la sucursal, acceso con
credenciales del trabajador brindadas por la empresa), **POS web** (el
cliente autogestiona su propia atención), **POS kiosko** (el cliente
autogestiona su propia atención en un kiosko instalado en la sucursal).

Objetivo: agilizar y trazar la atención de órdenes de compra en sucursal,
evitando stock negativo y centralizando pagos y emisión de comprobantes.

Responsabilidades: interconectarse con inventarios, productos comerciales,
medios de pago, clientes, listas de precio y emisión de comprobantes;
interconectarse con otros puntos de venta de la misma sucursal (evita stock
negativo, facilita el trabajo); autorizar pagos/cobros digitales (tarjeta,
billeteras digitales); aceptar efectivo solo si el trabajador está
designado como cajero; emitir comprobantes/facturas de forma local; crear
trazabilidad con timestamps y registros; dar acceso a datos/registros de
ventas por fecha a un usuario, si la empresa lo autoriza; exigir apertura de
caja (monto de fondo/caja chica) antes de operar, si es cajero; exigir
cierre de caja al finalizar. Si el punto de venta es de autoatención, exige
pago adelantado antes de enviar el pedido a preparación; si es de atención
en mesa, el pago puede realizarse al finalizar el consumo.

Relaciones: pertenece a una sucursal; se accede con credenciales de
trabajador (hardware) o de forma autogestionada (web/kiosko); está
interconectado con otros POS de la misma sucursal; la página web factura
por su propia cuenta, pero descuenta inventario de la sucursal a la que
apunta la compra (por cercanía al delivery o elección de take-out del
cliente).

Restricciones: solo el cajero, el kiosko y la página web pueden emitir
comprobantes (para adjudicar responsabilidad y verificar cobros
correctamente); solo acepta efectivo si el trabajador está designado como
cajero; no se activa sin que el cajero ingrese el monto de fondo/caja
chica; no se cierra sin cumplirse la hora de cierre del establecimiento y
sin cuadre 100% de efectivo/tarjetas/billetera digital — si hay descuadre,
se advierte al cajero, y si este confirma el monto, se genera un reporte
para contabilidad, que le aplica el descuento correspondiente.

Configurable en el ERP: hardware asignado por sucursal, credenciales de
trabajador, medios de pago habilitados, política de pago-antes-de-
preparación (autoatención vs. atención en mesa), autorización de acceso a
datos históricos de ventas por usuario, monto de apertura de caja.

> La Caja de POS no es un concepto aparte: es la función de apertura/cierre
> y arqueo del propio Punto de Venta, ya descrita arriba. Los flujos de
> apertura y cierre se detallan más adelante en
> [workflows.md](../domain/workflows.md).

### Central de Pedidos

Similar a un punto de venta, pero puede estar asociada a múltiples marcas,
sucursales y ciudades. Atendida por agentes humanos y/o de IA. Recepciona
comunicaciones de clientes por WhatsApp, mensajería, llamadas telefónicas y
correo electrónico.

Objetivo: canalizar comunicaciones multicanal de clientes, generar pedidos
y conectarlos con la marca y sucursal correspondiente para su producción y
entrega.

Responsabilidades: recepcionar comunicaciones de WhatsApp, mensajería,
llamadas telefónicas y correo electrónico; canalizar y atender esas
comunicaciones; generar pedidos; hacer upsell; conectar con la marca y
sucursal correspondiente para enviar la orden; mantener información
actualizada de precios e inventarios, garantizando que el pedido pueda
producirse con todos los productos comerciales solicitados; generar
timestamps y trazabilidad de los agentes; resolver dudas, reclamos y quejas
(rol asociable); emitir links de pago, o coordinar el pago con el punto de
venta en la sucursal; aceptar anulaciones hasta 5 minutos después de
emitido el pedido, coordinando con la sucursal vía ERP; determinar el
tiempo de espera del pedido según los cálculos del sistema sobre
saturación/carga del local y la ruta de entrega; escalar un problema de
pedido, tiempos o calidad a un supervisor o encargado de sucursal,
generando un reporte de escalamiento.

Métrica de efectividad: tiempo de atención y efectividad de upsell.

Relaciones: puede asociarse a múltiples marcas, sucursales y ciudades; es
atendida por agentes humanos y/o de IA; conecta con la marca y sucursal
correspondiente para enviar cada orden — en delivery, el sistema decide la
sucursal según cercanía de la zona al destino del pedido; en take-out, el
cliente elige según su propia conveniencia; coordina el pago con el punto
de venta de la sucursal, cuando aplica.

Restricciones: no tiene acceso a las ventas de otras sucursales o marcas;
solo acepta anulaciones dentro de los 5 minutos posteriores a la emisión
del pedido, coordinadas con la sucursal vía ERP.

Configurable en el ERP: marcas, sucursales y ciudades asociadas, canales
habilitados, rol de soporte (dudas/reclamos/quejas) activado o no, ventana
de anulación (5 minutos).

## Pendiente de definición (con el negocio)

- Mecanismo formal de resolución de conflicto de interés entre empresas
  miembro.
- Criterios objetivos para "beneficiar/perjudicar" a una empresa miembro
  (ver `RN-GRP-001` en [business-rules.md](../domain/business-rules.md)).
- Proceso de aprobación unánime de la sociedad (quórum, actas) para venta de
  propiedad intelectual.
- Si terceros externos pueden ser accionistas o solo dirección delegada.
- Criterio objetivo de "afectar la rentabilidad del grupo" (restricción de
  contratación de terceros externos por una empresa).
- Qué pasa si una empresa entra en pérdida sostenida (¿el grupo interviene?).
- Mecanismo formal de licenciamiento marca-empresa (¿contrato interno,
  regalías, condiciones?).
- Proceso de aprobación de excepción por estudio comercial (adaptación de
  producto de marca al mercado local).
- Gobernanza de rebranding/innovación de marca (¿quién decide, quién
  financia?).
- Naming exacto: "La Avenida" vs. "La AveNida" (usado así en un mensaje).
- Área específica que autoriza/paga suministros directos de proveedor (gas,
  bebidas embotelladas) a una sucursal.
- Proceso formal de estudio de mercado/viabilidad para abrir o cerrar una
  sucursal (documentos, aprobación).
- Protocolo de bioseguridad y qué entidades califican como "personal
  fiscalizador".
- Plantillas por tipo de Documento (estructura/campos exactos) para
  automatizar su emisión — a definir junto al negocio.
- Condiciones de seguridad de transporte para traspasos urgentes entre
  sucursales (relación con Almacén de Transporte).
- Qué pasa con el almacén de sucursal cuando esta cambia de marca (¿se
  vacía, se transfiere?).
- Estándar exacto de homologación entre cocinas de producción del grupo.
- Criterios de demanda predictiva usados para programar producción.
- Protocolo detallado de eliminación de plagas en cocina de producción
  (quién ejecuta, tiempos, validación antes de reanudar).
- Vida útil/rotación del almacén transitorio de la cocina de producción.
- Criterios objetivos de "características similares" para definir una
  región (qué variables se miden).
- Quién aprueba finalmente el ingreso a una nueva región (¿holding, comité?).
- Listado de regiones actuales/planeadas del grupo.
- Criterios objetivos de "densidad poblacional alta"/"mercado dinámico"
  para calificar una ciudad como válida para el grupo.
- Quién aprueba el ingreso a una nueva ciudad (¿las mismas 4 áreas que
  región?).
- Listado de ciudades actuales donde opera el grupo.
- Proceso de reclasificación de una zona/área de servicio (ej. de
  restringida a limitada).

## Principios del producto

- Multi-marca / multi-sucursal con contexto de tenant en toda consulta.
- Pedidos por agente humano o **agente de IA** (mismo contrato, mismos permisos).
- Trazabilidad total: todo movimiento auditado (quién, qué, cuándo, dónde).
- Corre igual en Docker local y en servidor.
- Integraciones: Nubefact (SUNAT), Izipay (pagos), Google API, Meta API.
