# Reglas de negocio

Validaciones, restricciones, cálculos y políticas funcionales. Cambian más
seguido que las entidades ([domain-model.md](domain-model.md)); derivan de los
principios invariantes ([../foundation/business-philosophy.md](../foundation/business-philosophy.md)).
Cada regla usa la terminología oficial del
[glosario](../foundation/glossary.md).

Formato: `[RN-área-nnn] enunciado`. Las reglas se implementan en el `domain/`
de su módulo y se prueban de forma aislada.

## Región

- **RN-REG-001** No se ingresa a una nueva región sin el análisis de
  viabilidad y estrategia de las áreas de marketing, finanzas, operaciones
  y comercial del grupo empresarial.

## Ciudad

- **RN-CIU-001** No se ingresa a una nueva ciudad sin investigación de
  mercado.

## Zona / Área de servicio

- **RN-ZON-001** Un área restringida no se atiende.
- **RN-ZON-002** Un área limitada solo se atiende dentro de sus
  restricciones horarias o climáticas.
- **RN-ZON-003** Un área fuera de servicio no se atiende.
- **RN-ZON-004** Solo la empresa traza y define geocercas, y decide qué
  áreas son limitadas y cuáles restringidas.

## Punto de venta (POS)

- **RN-POS-001** Solo el cajero, el kiosko y la página web pueden emitir
  comprobantes.
- **RN-POS-002** Un POS solo acepta efectivo si el trabajador está
  designado como cajero.
- **RN-POS-003** Un POS no se activa sin que el cajero ingrese el monto de
  apertura de caja (fondo/caja chica).
- **RN-POS-004** Un POS no se cierra sin cumplirse la hora de cierre del
  establecimiento y sin cuadre 100% de efectivo/tarjetas/billetera digital;
  ante descuadre confirmado por el cajero, se genera un reporte para
  contabilidad que le aplica el descuento correspondiente.
- **RN-POS-005** Un POS de autoatención exige pago adelantado antes de
  enviar el pedido a preparación; uno de atención en mesa permite pagar al
  finalizar el consumo.
- **RN-POS-006** La página web factura por su propia cuenta, pero
  descuenta inventario de la sucursal a la que apunta la compra.
- **RN-POS-007** Al cierre, la caja chica (fondo) se cuenta y registra por
  denominación (cantidad de cada billete y moneda); toda diferencia contra
  el monto y denominación de apertura se registra igual que un descuadre de
  ventas (RN-POS-004).
- **RN-POS-008** Los pagos por link de pago se verifican automáticamente
  por el sistema al cierre, filtrados por sucursal, y se computan solo en
  la caja principal de la sucursal cuando esta tiene más de una caja.
- **RN-POS-009** El área contable mantiene al menos un POS de pago con
  tarjeta de emergencia por grupo de sucursales cercanas, para cubrir
  fallas o escasez por demanda.
- **RN-POS-010** Todo POS de pago con tarjeta está inventariado por el
  área contable con número de serie y código de comercio.
- **RN-POS-011** La apertura de caja no se bloquea por faltante de
  efectivo, escasez de sencillo (billetes/monedas de baja denominación) o
  un POS de pago con tarjeta averiado: la caja abre en el horario normal
  dejando constancia en el reporte a contabilidad y gerencia, y el
  problema se resuelve en paralelo.
- **RN-POS-012** El encargado de tienda/supervisor es responsable de
  prever sencillo suficiente para la jornada siguiente y de entregarlo al
  cajero en la apertura de caja.
- **RN-POS-013** Durante el conteo de efectivo y la apertura de caja, el
  encargado de tienda/supervisor no puede atender otro proceso o
  actividad.
- **RN-POS-014** La pantalla del punto de venta se bloquea a los **5
  minutos** sin actividad y se reabre con el PIN de quien tiene la sesión.
  El bloqueo **no cierra sesión**: la caja abierta y el pedido a medio
  armar siguen donde estaban — un bloqueo que hiciera perder el pedido se
  eludiría dejando la pantalla tocada a propósito. Los PIN del punto de
  venta se teclean en un teclado numérico sin campo de formulario, para que
  el navegador no pueda ofrecer guardarlos: un PIN guardado en la caja es
  la vía por la que un turno entra con la cuenta del anterior y toda la
  auditoría (RN-AUD-005) nombra a la persona equivocada. Un intento
  fallido de desbloqueo cuenta contra el mismo bloqueo de cuenta que el
  ingreso.

## Central de pedidos

- **RN-CTP-001** Una central de pedidos no tiene acceso a las ventas de
  otras sucursales o marcas fuera de las que gestiona.
- **RN-CTP-002** Solo se acepta una anulación dentro de los 5 minutos
  posteriores a la emisión del pedido, coordinada con la sucursal vía ERP.
- **RN-CTP-003** En delivery, el sistema asigna la sucursal según cercanía
  de la zona de servicio al destino del pedido; en take-out, el cliente
  elige la sucursal.
- **RN-CTP-004** Todo escalamiento de un pedido (tiempos, calidad,
  problema) genera un reporte de escalamiento y se dirige a un supervisor o
  encargado de sucursal. **Implementado desde ADR-036**: la cadena es
  `reporte_escalamiento` y el nivel `supervisor` resuelve al encargado de
  turno (con roles `supervisor`/`admin` de respaldo si no hay caja abierta).
  Alcance de hoy: solo se escala lo que el catálogo cerrado emite, así que los
  motivos `queja`, `error_sistema` y `desistimiento_no_resuelto` se pueden
  elegir pero ninguna emisión los produce todavía.

## Canal de venta

- **RN-CNV-001** El mantenimiento de un canal de venta es responsabilidad
  de la empresa; su promoción es responsabilidad del área de marketing
  del grupo empresarial.
- **RN-CNV-002** La participación en los ingresos de cada canal la mide y
  analiza el área comercial.
- **RN-CNV-003** Un canal operado por humano exige capacitación del
  operador y herramientas funcionales completas.

## Modalidad de consumo

- **RN-MDC-001** Las modalidades de consumo habilitadas (mesa, takeout,
  delivery) son configurables por sucursal, marca o canal de venta;
  pueden ofrecerse en cualquier combinación.
- **RN-MDC-002** Cada modalidad de consumo exige un número mínimo de
  datos del cliente para aceptar el pedido (nombres, DNI, teléfono,
  dirección, medio de pago), variable según la modalidad.
- **RN-MDC-003** El precio de un producto comercial o servicio puede
  variar según la modalidad de consumo.

## Carrito

- **RN-CAR-001** El carrito reserva temporalmente el stock de los
  productos seleccionados; si el cliente desiste, el stock reservado
  vuelve a disponible.
- **RN-CAR-002** Si el punto de venta admite pedidos abiertos pendientes
  de pago, el pedido va a KDS antes del pago; si no los admite, el
  carrito va primero a la pasarela de pago, y solo al efectuarse el pago
  el pedido va a KDS y se emite el comprobante.

## Medio de pago

- **RN-MDP-001** Un medio de pago a crédito puede tener una lista de
  precios distinta a la del pago al contado.
- **RN-MDP-002** El efectivo sigue una cadena de custodia obligatoria:
  cajero → encargado de tienda/supervisor → área contable (verifica y pone
  a disposición de la empresa). En la apertura, el fondo recorre la misma
  cadena en sentido inverso. **Cada relevo, en cualquier sentido, exige que
  quien recibe se autentique con usuario y PIN en el ERP y confirme que los
  valores son correctos.**
  *Enmendada el 2026-08-15 (RN-MDP-008, ADR-049)*: lo que se firma es **el
  traspaso del efectivo**, no el acto de abrir o cerrar el turno. Abrir y
  cerrar son conteos que el cajero hace solo; el relevo firmado ocurre
  cuando la plata cambia de manos, que puede ser horas después del cierre.
- **RN-MDP-003** Un pago a crédito con otra empresa lo regulariza el área
  contable.
- **RN-MDP-004** Ante disconformidad o duplicidad de un cobro, el área
  contable emite una carta formal con: operación, fecha, hora, cliente,
  referencia de pago, lote, monto, y procedencia del pago (o su
  ausencia).
- **RN-MDP-005** El faltante detectado en el cierre de caja se atribuye
  según en qué etapa se detecta y documenta: si el cajero o el encargado de
  tienda/supervisor lo detectan y documentan en el reporte de cierre o de
  validación, el responsable es el cajero — salvo que este haya reportado
  antes un cobro mal hecho por un tercero (delivery/compañero, ver
  RN-COM-005 / PROC-COM-002), en cuyo caso el responsable es ese tercero.
  Si el faltante recién aparece en el área contable, sin haber sido
  documentado antes, el responsable es el encargado de tienda/supervisor,
  por no detectarlo en su validación.
- **RN-MDP-006** El fondo/caja chica puede resguardarse en la sucursal
  (caja fuerte del encargado de tienda/supervisor) entre el cierre y la
  siguiente apertura de caja, solo si el local cuenta con cámaras, caja
  fuerte y alarma, y el área contable determina que el monto es bajo. En
  caso contrario (local inseguro, alto volumen de venta en efectivo, o
  necesidad de cambiar denominaciones) el encargado de tienda/supervisor
  traslada el efectivo a las oficinas del área contable y lo recoge para
  la siguiente apertura.
- **RN-MDP-007** Todo **ingreso o retiro de efectivo del cajón durante el
  turno** (pagar a un repartidor, comprar hielo, reponer un vuelto) se
  registra con **motivo obligatorio** y entra al cálculo del monto esperado
  del cierre. Sin registrarlo, el cierre cuadra contra un esperado irreal y
  el descuadre se le atribuye al cajero (RN-MDP-005). **Retirar exige
  autorización de supervisor**; ingresar no, porque meter plata al cajón no
  es la operación de la que hay que desconfiar. Un retiro nunca puede
  exceder el efectivo disponible: el cajón no da crédito.
- **RN-MDP-008** **El cajero abre y cierra su turno de caja solo.** Le basta
  su propio permiso de operar caja: no hace falta la firma de un encargado
  ni de nadie más. Lo que prueba cuánto había en el cajón es el conteo por
  denominación (RN-POS-003/007), no una firma — y exigir que un encargado
  viniera a poner su PIN en cada apertura terminaba, en el local, con la
  sesión del encargado abierta en la caja todo el turno, que es peor que no
  pedir nada.
  **Al cerrar, el efectivo queda en el cajón a nombre del cajero.** La
  entrega al encargado de tienda/supervisor es un acto **posterior y
  aparte**, y esa sí la firma quien recibe con su usuario y PIN
  (RN-MDP-002). Mientras no la firme nadie, el responsable del faltante
  sigue siendo el cajero (RN-MDP-005): dar por entregado lo que sigue en el
  cajón le atribuiría la plata a alguien que no la tocó.

## Impuestos

- **RN-IMP-001** El consumo/operación dentro de la región amazónica está
  exonerado de IGV y sujeto a tasa reducida de IR (Ley 27037); fuera de
  la región, IGV aplica normalmente.
- **RN-IMP-002** El IGV en compras a proveedores es configurable por
  proveedor, según si opera dentro o fuera de la región amazónica.
- **RN-IMP-003** Las compras de insumos/servicios sujetos a SPOT exigen
  el depósito de detracción en el Banco de la Nación antes de usar el
  crédito fiscal correspondiente.
- **RN-IMP-004** El predial y los arbitrios municipales aplican solo a
  sucursales con tenencia `propia`.
- **RN-IMP-005** La configuración y el pago de impuestos son
  responsabilidad del área contable o de asesores contables externos.
- **RN-IMP-006** El ITAN grava el excedente de activos netos de la
  empresa por encima del umbral legal vigente; su pago es aplicable como
  crédito contra el IR del ejercicio.

## Precio

- **RN-PRC-001** El precio no debe superar el valor percibido por el
  consumidor, ni estar por debajo del costo.
- **RN-PRC-002** El precio lo estudian las áreas comercial, contable e
  I+D+i.
- **RN-PRC-003** En puntos de venta de sucursal, kiosko y web, los
  precios son fijos e innegociables; solo varían por ofertas, descuentos
  o condiciones establecidas por la marca o el grupo, vía lista de
  precios.
- **RN-PRC-004** El precio se expresa en una sola divisa: la moneda
  oficial del país.
- **RN-PRC-005** La lista de precios la crea el área comercial, con
  asesoría del área contable.

## Promoción

- **RN-PRM-001** Una promoción la determinan las áreas comercial,
  marketing y contabilidad; incluye comunicación, material promocional,
  capacitación del personal, y un tiempo de duración definido.
- **RN-PRM-002** Una promoción debe estar dentro del guion de atención
  del personal de atención al cliente.

## Programa de puntos

- **RN-PTS-001** El cliente es una entidad a nivel de Grupo Empresarial
  (excepción explícita a RN-GEN-003): puede acumular y canjear puntos en
  cualquier canal de venta y cualquier marca del grupo.
- **RN-PTS-002** Los puntos se acumulan según el producto comercial
  consumido; el valor por producto o por monto lo determinan las áreas
  comercial y de marketing.
- **RN-PTS-003** Los puntos tienen una vigencia; al vencer, expiran.
- **RN-PTS-004** Para registrar a una **persona natural** basta el
  **teléfono**: no todo cliente quiere dar su DNI en el mostrador, y
  negarse a registrarlo por eso pierde la venta y su historial. El
  documento se completa después sin trámite
  (`PATCH /sales/clientes/{id}/documento`). Para **facturar a una empresa
  el RUC sí es obligatorio** — sin él no hay factura. La **primera vez**
  que un RUC o DNI se registra (persona/RUC nuevo, no reutilización de uno
  ya existente) el nombre/razón social sale de la **consulta RUC/DNI de
  Factiliza** (ADR-005) en vez de confiarse en lo tecleado en caja; si
  Factiliza no responde o no encuentra el documento, se usa lo tecleado —
  el alta nunca se bloquea por un proveedor externo caído.
- **RN-PTS-005** Un cliente **sin documento**, o con el genérico
  `00000000`, **no cuenta como cliente registrado con documento**: compra,
  recibe su boleta a su nombre y figura en el historial, pero queda **fuera
  de las promociones y beneficios reservados a clientes identificados**. Sin
  esta distinción cualquier boleta anónima entraría al programa de puntos.
  La condición es derivada (`rules.cliente_identificado`), no una columna:
  guardar el mismo hecho dos veces solo crea la ocasión de que se
  contradigan.
- **RN-PTS-006** En caja el cliente se busca por **teléfono, documento o
  nombre** — lo que recuerde en el momento
  (`GET /sales/clientes/buscar?q=`). Una misma persona es cliente a lo más
  una vez por grupo: registrarla dos veces partiría su historial.
- **RN-PTS-007** El padrón **se baja, se edita y se vuelve a subir** en el
  mismo formato, con revisión en el medio (ADR-051). La identidad de una fila
  es su `ID` o, si va vacío, su **número de documento**. El tipo sigue sin
  declararse: lo decide el documento (RN-PTS-002). De un cliente **natural**
  que ya existe la planilla solo puede **completar el documento**: su nombre,
  su teléfono y su dirección viven en su `persona` (RN-GEN-007) y se corrigen
  desde ahí — una fila que los cambie se informa con ese enlace, no se aplica
  a medias. La carga masiva **no consulta a SUNAT ni a RENIEC**: trescientas
  filas serían trescientas llamadas externas contra una cuota, así que el
  nombre del archivo manda; cuando el cliente se edita de a uno, SUNAT vuelve
  a mandar (RN-PTS-004). Administrar el padrón es un permiso propio
  (`sales.gestionar_clientes`), distinto del que tiene el cajero para
  registrar a alguien en el mostrador.

## Grupo empresarial

- **RN-GRP-001** Ninguna empresa miembro del Grupo puede ser beneficiada en
  perjuicio de otra.
- **RN-GRP-002** No puede generarse competencia desleal entre empresas
  miembro, ni de estas hacia terceros.
- **RN-GRP-003** Toda auditoría a empresas del Grupo se realiza con la misma
  calidad y profundidad, sin excepciones.
- **RN-GRP-004** Información interna de una empresa del Grupo no puede
  compartirse con terceros fuera del Grupo.
- **RN-GRP-005** Las empresas de soporte (logística, transporte, servicios)
  que atiendan terceros no pueden exponer inteligencia interna (know-how,
  procesos, datos) de las empresas del Grupo.
- **RN-GRP-006** Venta de propiedad intelectual del Grupo requiere aprobación
  unánime de la sociedad.

## Empresa

- **RN-EMP-001** Una empresa no puede dejar de ser parte del Grupo Empresarial.
- **RN-EMP-002** Una empresa no puede vender ni compartir información interna
  ni de clientes con terceros fuera del grupo.
- **RN-EMP-003** Una empresa no puede evadir impuestos ni saltarse la
  legislación del área donde opera.
- **RN-EMP-004** Una empresa no puede contratar servicios/sistemas/soporte de
  terceros externos si eso afecta la rentabilidad del grupo.
- **RN-EMP-005** Una empresa debe operar sin afectar su propia rentabilidad.
- **RN-EMP-006** Todo préstamo solicitado por una empresa requiere estudio de
  viabilidad previo del área contable (monto, motivo, tasas, plazos).

## Marca

- **RN-MAR-001** Una marca no posee activos tangibles; los posee la empresa
  licenciataria que la opera.
- **RN-MAR-002** Una marca solo puede vender sus propios productos
  comerciales/servicios, salvo excepción sustentada en estudio comercial
  (agencia/consultoría externa) que adapte características al mercado local.
- **RN-MAR-003** Toda empresa licenciataria de una marca debe seguir los
  procesos, recetas y protocolos definidos por esa marca.
- **RN-MAR-004** Una marca solo puede ser modificada (identidad, carta,
  procesos) por la empresa dueña del holding, a través del área de manejo de
  marca.

## Gerencia — dirección y gobierno

- **RN-GER-001** El Gerente General ejerce por facultades **delegadas por
  los socios**; las decisiones reservadas a la sociedad —venta de
  propiedad intelectual (RN-GRP-006), modificación de marca (RN-MAR-004),
  incorporación o salida de una empresa del Grupo (RN-EMP-001)— no las
  toma solo.
- **RN-GER-002** Toda aprobación/rechazo de una propuesta escalada y toda
  directiva gerencial se registra en un **acta de decisión gerencial**
  (quién decide, qué, cuándo, sustento, condiciones), archivada en el
  ERP; una decisión verbal no tiene validez operativa.
- **RN-GER-003** La **matriz de aprobaciones** (política de Gerencia) es
  la fuente única de qué requiere visado gerencial, su umbral y el
  aprobador; ninguna área fija un umbral propio por fuera de ella.
- **RN-GER-004** Un directivo con interés personal o parte relacionada en
  una propuesta se **abstiene** de aprobarla y deriva la decisión a otro
  nivel (alinea RN-GRP-001: sin trato preferente).
- **RN-GER-005** Gerencia **decide/ordena** la acción correctiva o
  disciplinaria cuando la situación lo amerita, pero su **ejecución
  formal la realiza el área competente** con el debido proceso: la
  sanción a un trabajador la ejecuta RRHH (RN-RRHH-004), nunca aplicada
  directamente por Gerencia saltando el proceso.
- **RN-GER-006** La entrada a un nuevo mercado, marca o línea de negocio
  requiere **estudio previo** documentado (mercado + viabilidad
  económica); Gerencia decide con sustento, no por intuición — usa el
  estudio de mercado de Comercial y la viabilidad económica de
  Contabilidad (mismo principio que RN-EMP-006).
- **RN-GER-007** El **presupuesto anual** de cada área se define en una
  reunión anual de presupuesto: cada área presenta su propuesta, Gerencia
  la revisa y designa el presupuesto del año. Dentro de su presupuesto
  aprobado y **bajo el límite** definido, cada área ejecuta el gasto de
  forma autónoma (sin aprobación puntual); **sobre el límite o fuera de lo
  presupuestado**, requiere aprobación puntual de Gerencia (matriz de
  aprobaciones, RN-GER-003). Los límites por área se definen en esa
  reunión (`[[ COMPLETAR ]]`).
- **RN-GER-008** Todo valor operativo que varía por empresa o en el tiempo
  —rango salarial de un perfil de puesto,
  margen de error de ajuste de inventario, monto del fondo de caja chica,
  plazos internos, y cualquier otro que hoy aparezca como
  `[[ COMPLETAR ]]` en un documento— se configura en `parametro_empresa`
  (entidad transversal, `data-model.md` §8c), **nunca hardcodeado en
  código ni fijado una sola vez en un documento de política**. Lo
  gestiona Gerencia; un cambio puede sustentarse en un `decision_gerencial`
  (acta) cuando amerite dejar constancia de por qué se cambió, pero el
  acta no es requisito para el ajuste rutinario de un valor ya
  configurado. Es **la única** tabla de configuración por empresa: los
  umbrales que gatillan una aprobación (RN-GER-003, ej. `purchases/oc_umbral`)
  también son filas suyas, con `valor={"monto": ...}` — `regla_aprobacion`
  se retiró el 2026-08-02.
- **RN-GER-009** Un cambio de parámetro operativo (RN-GER-008) lo **propone
  el área desde su propio módulo**, pero **no surte efecto hasta que
  Gerencia lo aprueba** en su sección de aprobaciones, donde puede
  aceptarlo, rechazarlo con motivo, o modificar el valor antes de aprobar.
  Mientras la propuesta está pendiente, el módulo consumidor sigue
  operando con el valor anterior. Aprobar deja constancia de quién propuso,
  quién resolvió, cuándo, y cuál era el valor anterior (`data-model.md`
  §8c, ADR-014).
- **RN-GER-010** Toda magnitud se expresa **con su unidad**: un monto lleva
  su **divisa** y una cantidad lleva su **unidad de medida**. Un número
  suelto (2000, 5) es ambiguo —¿soles o dólares? ¿kilos o unidades?— y en un
  valor que Gerencia aprueba esa ambigüedad se vuelve una decisión mal
  tomada. Los **decimales** con los que se redondea salen de esa unidad
  (`divisa.decimales`, `unidad_medida.decimales`), nunca de una constante en
  el código: hay monedas de 0 y de 3 decimales, y no es lo mismo pesar
  harina (gramos importan) que contar botellas (media botella no existe). La
  decisión gerencial registra la magnitud ya formateada con su unidad
  (`parametro_empresa.valor_display`, ej. "S/ 2000.00"), congelada al
  momento de decidir. En dinero el medio centavo **sube** (ROUND_HALF_UP).

## Sucursal

- **RN-SUC-001** Una sucursal opera exactamente una marca.
- **RN-SUC-002** Una sucursal se abastece del almacén central, salvo
  excepciones definidas (gas, bebidas embotelladas); aun en esos casos, la
  autorización y el pago los gestiona el área correspondiente, no la
  sucursal.
- **RN-SUC-003** El personal de sucursal no puede comprar ni pagar a
  proveedores sin autorización expresa de la empresa operadora.
- **RN-SUC-004** Un traspaso de urgencia de insumos entre sucursales solo se
  realiza vía ERP y cumpliendo las condiciones de seguridad de transporte
  del SKU.
- **RN-SUC-005** La apertura o cierre de una sucursal requiere estudio de
  mercado y viabilidad realizado por la holding o una consultora autorizada
  por esta.
- **RN-SUC-006** La apertura diaria de sucursal la inicia el encargado de
  tienda o supervisor, al menos 45 minutos antes de la hora de apertura al
  público. El checklist físico de apertura (agua, baños, plagas, fríos,
  gas) es una meta operativa de 5 minutos, sin bloqueo automático de la
  apertura.
- **RN-SUC-007** Durante la limpieza diaria y programada, el aire
  acondicionado permanece apagado (el polvo levantado por la limpieza
  acelera su deterioro); se enciende al finalizar la limpieza, como parte
  de la apertura de caja (junto con pantallas, extractores, luces
  decorativas y letrero).
- **RN-SUC-008** Ante rastros de plaga o baños sucios detectados en el
  checklist de apertura, la sucursal desinfecta a fondo la zona y reporta
  el incidente al área de Mantenimiento para que tome acción; no bloquea la
  apertura — a diferencia de la cocina de producción ante plaga
  (RN-CDP-002), que sí detiene operación.
- **RN-SUC-009** Ante falla de frío detectada en apertura, los SKUs
  comprometidos se marcan "NO USAR" (RN-ALS-004) y se trasladan a un frío
  distinto en buen estado. Si muestran descomposición, gas dentro del
  empaque o descongelación, quedan fuera de uso esa jornada, se reporta con
  urgencia a almacén central y gerencia (para decidir abastecimiento de
  urgencia o si se compromete la atención del turno), y se envían a
  almacén central con el repartidor si este llega tras el reporte. Si
  conservan el frío y no muestran abultamiento, se usan con normalidad esa
  jornada.
- **RN-SUC-010** Cada sucursal mantiene siempre un tanque de gas de
  repuesto. Al usarse el de repuesto, se genera un pedido urgente a
  Compras para reabastecimiento inmediato. Si no queda ninguno disponible,
  se contrata un proveedor de urgencia con el servicio. La falta de aviso
  previo sobre una carga baja (que deja a la sucursal sin repuesto) es
  responsabilidad sancionable del encargado de tienda o supervisor que no
  notificó.
- **RN-SUC-011** Ante corte de energía eléctrica, la sucursal usa motor o
  UPS de respaldo; ante falta de agua de red, abre el tanque de reserva.
- **RN-SUC-012** El supervisor y el encargado de tienda son ambos
  custodios de llave de la sucursal; si uno falta a la apertura, el otro
  debe ser notificado para asistir en su lugar.

## Documentos

- **RN-DOC-001** Todo documento tiene fecha de elaboración, un
  responsable que lo visa, un propósito, una fecha de entrega pactada, y
  debe ser veraz.
- **RN-DOC-002** El ERP y la empresa deben poder generar documentos de
  forma manual o automática.
- **RN-DOC-003** Todo proceso de la empresa incluye, entre sus pasos, la
  creación de documentos cuando haya información útil que registrar.
- **RN-DOC-004** El ERP y la empresa archivan y revisan los documentos
  generados.
- **RN-DOC-005** Toda solicitud (de cualquier tipo) registra fecha de
  ingreso, destinatario, emisor, detalle/cuerpo y lugar de origen; queda
  sujeta a aprobación o rechazo.
- **RN-DOC-006** Una orden es de ejecución obligatoria y unidireccional
  (de un ente superior a uno subordinado); no admite aprobación/rechazo
  como la solicitud. El pedido de un cliente, una vez confirmado en el
  punto de venta, es una Orden de Pedido, no una Solicitud.
- **RN-DOC-007** Una cotización no obliga al solicitante a comprar; solo
  informa costos.
- **RN-DOC-008** Una cotización recibida de un proveedor la solicita el
  área de compras y la evalúa el área de contabilidad y finanzas.
- **RN-DOC-009** Una cotización emitida por la empresa (a pedido de un
  cliente) la emite el área comercial, según el tarifario, la lista de
  precios y el rango de negociación admitido por la empresa.
- **RN-DOC-010** El reporte de producción se genera automáticamente al
  finalizar una jornada, con los datos que los usuarios fueron llenando
  durante la jornada, y debe ser visado por el encargado o jefe de cocina
  responsable.
- **RN-CPP-001** La empresa solo emite boleta o factura como comprobante
  de pago propio.
- **RN-CPP-002** La empresa acepta como comprobante de un egreso: factura,
  RHE, y excepcionalmente boleta o ticket de compra.
- **RN-CPP-003** Todo comprobante de pago se sustenta con un ingreso en
  efectivo, un voucher del proveedor de medios de pago, movimientos
  bancarios, o un contrato que autoriza un crédito. El **tipo** lo decide
  el documento que el cliente da en caja: **11 dígitos (RUC) obliga
  factura**; 8 dígitos (DNI), `00000000` o sin documento van a **boleta**.
  No hace falta que el cliente esté registrado — el receptor tecleado se
  guarda en el propio comprobante (ADR-018). Un documento con otro largo
  se rechaza antes de enviarse a SUNAT.
- **RN-CPP-004** No puede realizarse una venta sin la emisión de un
  comprobante de pago.
- **RN-CPP-005** Todos los comprobantes de pago son recepcionados y
  procesados por el área de contabilidad.
- **RN-CPP-006** Los pagos a proveedores los realiza el área de
  contabilidad, según lo pactado en el contrato o lo solicitado según la
  cotización.
- **RN-CPP-007** El número de serie de un comprobante se asigna por punto
  de venta, con correlativo propio; los comprobantes son propios de cada
  empresa y no se repiten dentro de ella.
- **RN-CPP-008** El ERP o el proveedor de facturación debe garantizar un
  mecanismo que impida duplicados o reemisiones de un comprobante.
- **RN-CPP-009** Una venta ya cobrada **no se anula: se acredita**. La
  corrección es una **nota de crédito** con un motivo del catálogo 09 de
  SUNAT, emitida contra un comprobante **aceptado** y **una sola vez** por
  documento; numera en **serie propia**, distinta de la de la boleta o
  factura que corrige. Puede ser **total** (acredita el comprobante entero)
  o **parcial por ítem**, y ninguna acredita más de lo que quede sin
  acreditar de esa línea. Tres consecuencias se deciden al emitirla, porque
  no hay respuesta universal:
  1. **La devolución del insumo es opcional** — un plato devuelto en cocina
     rara vez vuelve al inventario; quien acredita declara si repone.
  2. **El motivo decide si la venta muere**. Anulación (01) y devolución
     (06/07) la dan de baja; los motivos de corrección de datos —error en
     el RUC (02), error en la descripción (03)— **no**: la operación
     ocurrió, el papel estaba mal, y el comprobante queda anulado solo para
     poder reemitir el corregido.
  3. **Una nota rechazada por SUNAT no corrige nada**: queda registrada con
     su motivo de rechazo y la venta sigue exactamente como estaba.
  Acreditar devuelve dinero: exige permiso propio, no el del cajero que
  emitió (`sales.emitir_nota_credito`).
- **RN-GDR-001** Toda guía de remisión contiene fecha de inicio de
  traslado, bienes y cantidades transportadas, RUC del emisor y del
  receptor, lugar de origen y destino, motivo del traslado, y datos del
  transporte (chofer, vehículo).
- **RN-GDR-002** La guía de remisión la emite el área de almacén.
- **RN-GDR-003** Todas las guías de remisión se almacenan y resguardan en
  el área de contabilidad.
- **RN-CTR-001** Todo contrato requiere consentimiento de ambas partes, un
  objeto sobre el cual trata, y un motivo lícito.
- **RN-CTR-002** Todo contrato emitido por la empresa usa una plantilla,
  debe ser visado por un abogado, y se actualiza según los reglamentos y
  leyes del país.
- **RN-CTR-003** Un contrato lo suscribe el área correspondiente según sus
  facultades y necesidades, autorizado por gerencia.
- **RN-CTR-004** Todo contrato se registra en el ERP.

## Recursos humanos

- **RN-RRHH-001** La boleta de pago refleja la planilla electrónica
  (PLAME) y se entrega a más tardar el 3.er día hábil del mes siguiente;
  el trabajador la firma o recibe con constancia (electrónica válida).
- **RN-RRHH-002** El certificado de trabajo se emite al cese dentro de 48
  horas; indica tiempo de servicios y cargo(s), y —a solicitud del
  trabajador— conducta y desempeño.
- **RN-RRHH-003** La liquidación de beneficios sociales se paga dentro de
  48 horas del cese (CTS, vacaciones y gratificación truncas, otros
  adeudos).
- **RN-RRHH-004** Una amonestación escrita respeta proporcionalidad,
  inmediatez, razonabilidad y non bis in idem, y da derecho al descargo
  del trabajador; es escalón previo a suspensión o despido.
- **RN-RRHH-005** Una solicitud de vacaciones/licencia/permiso queda
  sujeta a aprobación; las vacaciones son 15 días calendario por año
  mientras la empresa esté acreditada como microempresa en REMYPE (D.S.
  013-2013-PRODUCE); pasan a 30 días (D.Leg. 713) al salir del régimen.
- **RN-RRHH-006** Un pacto de permanencia por capacitación debe ser
  razonable y proporcional en plazo y monto de reembolso; el reembolso es
  proporcional al tiempo de permanencia no cumplido. Un pacto excesivo es
  nulo por vulnerar la libertad de trabajo.
- **RN-RRHH-007** Las cartas y actas de RRHH se generan desde plantillas
  versionadas, rellenadas con datos del ERP más campos manuales, y visadas
  por abogado antes de su uso (extiende RN-CTR-002).
- **RN-RRHH-008** Un `trabajador` (vínculo laboral) es distinto de un
  `usuario` (identidad de login); pueden existir por separado.
- **RN-RRHH-009** Un trabajador que no marca su entrada en el ERP no se le
  considera el día o las horas no marcadas.
- **RN-RRHH-010** Tardanza del encargado de tienda o supervisor a la
  apertura, sin aviso previo de al menos 24 horas ni coordinación con un
  supervisor: si retrasa la apertura hasta 30 minutos, recibe memorándum
  (no es sanción); si la retrasa más de 30 minutos, o si es una falta (no
  asistencia), recibe carta de amonestación (RN-RRHH-004) y asume la
  responsabilidad documentada.
- **RN-RRHH-011** Ante personal faltante en la apertura, el personal
  restante cubre sus funciones mientras se busca un reemplazo disponible en
  otra sucursal o en su día de descanso. El reemplazo recibe pago extra,
  cuyo monto se descuenta al trabajador faltante — salvo que este presente
  constancia médica.
- **RN-RRHH-012** Ningún trabajador inicia labores sin contrato firmado y
  alta confirmada en T-Registro (SUNAT); el contrato a tiempo parcial
  además se comunica al MTPE dentro de 15 días de firmado.
- **RN-RRHH-013** Ninguna convocatoria se publica sin perfil de puesto
  aprobado ni con requisitos discriminatorios (edad, sexo, apariencia,
  estado civil, religión — Ley 26772). *Aplicada en código desde 2026-08-01
  en su mitad verificable: `publicar_convocatoria` rechaza la convocatoria
  sin `perfil_puesto`. Que el aviso no discrimine lo revisa una persona
  antes de publicar (SOP de publicación de convocatoria).*
- **RN-RRHH-014** El uniforme y EPP son condición de trabajo: se entregan y
  devuelven con acta firmada, y su movimiento se registra en el ERP como
  artículo de almacén.
- **RN-RRHH-015** Durante toda la jornada, el trabajador porta el uniforme
  **completo, limpio y presentable** (incluye EPP cuando el puesto lo
  exige). El incumplimiento reiterado es falta de conducta y se maneja
  por el proceso disciplinario (RN-RRHH-004).
- **RN-RRHH-016** No se contrata a personas con parentesco de primer o
  segundo grado (consanguinidad o afinidad) con un trabajador vigente del
  grupo, para prevenir conflicto de interés y trato preferente
  (RN-GRP-001). El parentesco sobreviniente a la contratación se declara
  y puede exigir reubicación para eliminar la relación de
  subordinación/control.
- **RN-RRHH-017** No se admiten relaciones sentimentales entre
  trabajadores del **mismo centro laboral**, ni ninguna relación
  sentimental que implique **subordinación directa** (jefe–subordinado).
  La relación preexistente o sobreviniente se declara; de existir
  subordinación o mismo centro, la empresa reubica para eliminar el
  conflicto de interés.
- **RN-RRHH-018** El trabajador no usa el **conocimiento de la empresa**
  (know-how, procesos, recetas, datos, cartera) para prestar servicios a
  terceros, ni **recursos de la empresa** (equipos, insumos, marca,
  tiempo pagado) para beneficio personal. Extiende la confidencialidad de
  RN-EMP-002/RN-GRP-004 y el criterio de conflicto de interés de
  RN-GER-004 al personal operativo; su infracción es falta grave.

## Auditoría

- **RN-AUD-001** Toda auditoría analiza exactitud de registros, eficiencia
  de procesos, controles internos, y cumplimiento de normativas, políticas
  y procesos.
- **RN-AUD-002** Una auditoría interna la realiza la propia empresa, a
  cargo del área donde se detecta el problema, o como rutina de
  supervisión/mejora continua.
- **RN-AUD-003** Una auditoría externa la realiza el grupo empresarial o
  una consultora externa, para obtener información imparcial y objetiva.
- **RN-AUD-004** Una auditoría se dispara por reportes de alarma de
  inconsistencias de inventario, alertas de malas prácticas, reclamos, o
  sanciones de entidades regulatorias.
- **RN-AUD-005** Hay acciones que un operario **pide** pero no puede
  **autorizar**: descontar sobre el total, quitar líneas ya enviadas a
  cocina, retirar efectivo del cajón, cerrar caja con diferencia. En esos
  casos el supervisor se identifica **en el mismo terminal, con su PIN**, y
  el sistema verifica su clave *y* que realmente tenga el permiso antes de
  habilitar la acción. Quién autorizó se deriva de esa verificación, nunca
  de un dato que el operario pueda escribir: un identificador suelto en el
  pedido es una firma falsificable, y el registro de quién autorizó
  —que es la razón de ser del control— dejaría de valer nada. La
  autorización es puntual: cubre una acción, no abre sesión, no se renueva
  y caduca en minutos.

## Dato

- **RN-DAT-001** Un dato no puede duplicarse ni omitirse; debe tener
  estructura y tipo homogéneo según su naturaleza.
- **RN-DAT-002** Rellenar un dato es responsabilidad del trabajador que lo
  origina; analizarlo es responsabilidad del área correspondiente.
- **RN-DAT-003** La disponibilidad del dato es responsabilidad del ERP.
- **RN-DAT-004** Un dato se almacena por tiempo indefinido.

## Archivo

- **RN-ARC-001** Un archivo puede vincularse a cualquier entidad de la
  base de datos del ERP.
- **RN-ARC-002** Un archivo se origina de dos formas: generado
  automáticamente por el ERP (con plantillas), o subido por el usuario.

## Evidencia

- **RN-EVD-001** Recopilar y proveer al ERP la evidencia suficiente para
  sustentar un hecho es responsabilidad del trabajador que lo reporta o
  eleva a la siguiente instancia.
- **RN-EVD-002** La evidencia enviada por un cliente (foto, video, audio)
  debe subirla el personal al ERP.

## Historial

- **RN-HIS-001** Todo historial debe poder verse en el ERP, ser fácil de
  ordenar y filtrar, y acotarse por rango de fechas.
- **RN-HIS-002** Un historial solo lo consulta personal con acceso
  autorizado.

## Personas y actores

- **RN-PER-001** Un practicante/pasante no genera vínculo laboral; su
  jornada no excede 6h/día ni 30h/semana; su subvención no es menor a 1
  RMV cuando cumple la jornada máxima; tiene derecho a EsSalud o seguro
  equivalente. No genera CTS, gratificaciones ni indemnización por
  despido arbitrario.
- **RN-PER-002** El personal por locación de servicios (RHE) no tiene
  horario fijo ni se le registra asistencia en el ERP; hacerlo es
  evidencia de subordinación y expone a la empresa a que SUNAFIL declare
  vínculo laboral retroactivo (con CTS, gratificaciones, vacaciones y
  EsSalud).
- **RN-PER-003** Un repartidor de plataforma externa no tiene vínculo
  laboral ni es gestionado como recurso propio de la empresa (no aplica
  Vehículo ni Mantenimiento); su marco legal en Perú es inexistente a la
  fecha (sin ley vigente sobre trabajadores de plataformas digitales).
- **RN-PER-004** Los datos de un postulante (CV, contacto) requieren
  consentimiento previo, informado y expreso para tratarse y conservarse
  (Ley 29733, D.S. 016-2024-JUS); el plazo de conservación se declara en
  el aviso de privacidad, no lo fija la ley; el postulante conserva sus
  derechos ARCO en cualquier momento.
- **RN-PER-005** Un cliente puede no tener datos registrados
  (`cliente_id` nulo); es un caso válido, no un error de captura.
- **RN-PER-006** El supervisor es superior jerárquico de los encargados de
  tienda de su marca (alcance RBAC: una marca, múltiples sucursales —
  `authorization.md`, a diferencia del encargado de tienda, limitado a la
  sucursal que se le encargó). Puede asumir las funciones del encargado de
  tienda cuando la situación lo amerite, y vela por el correcto
  funcionamiento operativo y el cumplimiento de reglas en las sucursales a
  su cargo.
- **RN-PER-007** El derecho de cancelación (Ley 29733) sobre `persona` se
  ejerce por **anonimización**, nunca por borrado físico —`trabajador`/
  `cliente`/`usuario` la referencian, y suele coexistir con una obligación
  de retención tributaria/laboral vigente que prevalece mientras dure.
  Antes de anonimizar, quien opera verifica manualmente que no haya
  `trabajador` en estado `activo` ligado a esa persona, ni comprobante bajo
  retención tributaria, ni litigio abierto — el sistema no lo bloquea
  automáticamente (ADR-011). Una persona ya anonimizada no admite
  rectificación (`PATCH` da 409).

## Transversales

- **RN-GEN-001** El stock nunca se edita directo: todo cambio es un
  `Movimiento` inmutable; el stock es su suma.
- **RN-GEN-002** Los documentos emitidos (OC, venta confirmada, comprobante,
  asiento) son inmutables; toda corrección va por documento inverso o anulación
  auditada. Nunca se borra información histórica.
- **RN-GEN-003** Toda acción ocurre dentro de un contexto de tenant
  (empresa/marca/sucursal) y se registra en auditoría.
- **RN-GEN-004** Los agentes de IA (`tipo=agente_ia`) obedecen exactamente las
  mismas reglas de dominio que un humano; solo cambian sus permisos.
- **RN-GEN-005** Todo Activo (artículo, activo no corriente, producto
  comercial, servicio) tiene un `id_interno` de 4 caracteres alfanuméricos,
  autogenerado por el ERP al crearse, inmutable e irrepetible.
- **RN-GEN-006** Dar de baja o descontinuar un Activo lo archiva (se oculta
  de listados); nunca se elimina de la base de datos.
- **RN-GEN-007** Los datos de una persona natural (nombres, apellidos,
  documento, domicilio) viven en una única entidad `persona`; `trabajador`,
  `cliente` y `usuario` la referencian y no duplican esos datos. Los roles
  de un documento (emisor, destinatario, representante, aprobador) se
  resuelven a una `persona` (vía `trabajador` cuando es personal interno)
  al momento de emitir.

## Productos y recetas

- **RN-PRD-001** Un producto comercial NUNCA es un artículo inventariable;
  siempre apunta a una receta.
- **RN-PRD-002** Al confirmarse una venta, la receta del producto descuenta sus
  insumos/subrecetas del almacén de la sucursal vendedora.
- **RN-PRD-003** Una subreceta es a la vez artículo inventariable y tiene su
  propia receta (BOM); puede consumirse o fabricarse.
- **RN-PRD-004** El sistema aplica los modificadores de un producto
  comercial siempre en el orden tamaño → combinación → extras → restas,
  sin importar el orden en que el cliente o trabajador los seleccionó.
- **RN-PRD-005** Toda configuración/modificador admitido por un producto
  comercial debe reflejarse en el punto de venta de la sucursal.
- **RN-PRD-006** Es obligatorio asignar un SKU al ingresar un producto
  inventariable nuevo; un SKU nunca se elimina.
- **RN-PRD-007** Cuando el SKU principal de un artículo llega a su stock
  mínimo, se genera una alerta; si no hay disponibilidad, se solicita a un
  proveedor un SKU alternativo, que solo se usa mientras dure la
  indisponibilidad del principal y cuyo abastecimiento retira la alerta del
  SKU principal.
- **RN-PRD-008** La creación o modificación de una receta o subreceta en
  el ERP la realiza el área de Producción o I+D.
- **RN-PRD-009** Toda modificación de receta o subreceta genera un reporte
  de modificación, actualiza costos, genera solicitud de actualización de
  manuales de recetas, y notifica con urgencia a las personas involucradas
  en su fabricación.
- **RN-PRD-010** Una receta puede marcarse flexible, permitiendo ajustar
  insumos por sabor o calidad; el criterio de ajuste lo asigna el área de
  Producción.

## Producción — cronograma, calidad y cocina

Spec a futuro (2026-07-20): documentada antes de existir físicamente —
la primera cocina de producción está planeada para 2027; hoy la
producción se hace en cocinas de sucursal. Ver
[docs/produccion/README.md](../produccion/README.md).

- **RN-PRD-011** La cocina de producción opera bajo un **plan de
  producción** (cronograma fijo por tipo de receta/proceso, ej. días y
  turnos), definido por Producción junto con Gerencia y Almacén según
  demanda. El plan se **ajusta por necesidad** (pedido urgente de Almacén
  Central por quiebre de stock, RN-PRD-007) sin reemplazar la
  planificación base — la orden de producción generada por necesidad
  también queda vinculada al plan vigente cuando aplica.
- **RN-PRD-012** El cronograma agrupa órdenes de producción por tipo de
  receta/proceso para evitar contaminación cruzada; no se alternan
  procesos incompatibles en la misma línea sin limpieza/desinfección
  intermedia documentada.
- **RN-PRD-013** Toda orden de producción pasa por **control de calidad**
  antes de habilitarse para despacho al almacén central. Ante un
  resultado no conforme, el jefe de cocina evalúa si el lote es
  corregible (reproceso) o debe desecharse — en ambos casos continúa en
  RN-PRD-014.
- **RN-PRD-014** Todo hallazgo de no conformidad de calidad genera un
  **reporte de escalamiento** (`reporte_escalamiento`, origen
  `produccion`), se corrija o se deseche el lote — nunca queda sin
  registro. El jefe de cocina redacta el hallazgo y la acción tomada;
  reincidencia por el mismo motivo escala a Comercial/Gerencia para
  revisión de receta o proceso, igual que el resto de reportes de
  escalamiento del ERP. Un solo asiento contable posible por hallazgo,
  según el estadio final: si se desecha, el registro de merma (RN-INV-017)
  es ese asiento; si se reprocesa, no hay merma ni asiento — el reporte
  solo detalla cómo se corrigió. **Implementado desde ADR-036**: el hallazgo
  emite `production.no_conformidad_detectada` y el escalamiento se abre sobre
  ese reporte, no sobre la orden — así conserva la foto, el actor y la doble
  puerta de RN-REP-002.
- **RN-PRD-015** La destrucción de un lote no conforme se realiza dentro
  del establecimiento, en zona cubierta por cámaras de videovigilancia
  (nunca fuera del local) y dentro del horario laboral. El video de la
  destrucción y el desecho final a la basura son la evidencia adjunta al
  reporte de escalamiento — previene sustracción del producto declarado
  como merma. Lo exige `reporte_escalamiento.evidencia_id` cuando el motivo es
  `no_conformidad_calidad` y la orden terminó en desecho; la validación vive en
  la capa de aplicación y no en un CHECK porque «terminó en desecho» es un
  campo de `orden_produccion`, otra tabla de otro módulo (ADR-036).
- **RN-PRD-016** El inventario de la cocina de producción (insumos,
  subrecetas en elaboración, producto terminado) sigue el mismo esquema
  de conteo cíclico y margen de error que Almacén Central (RN-INV-007/
  014/015), adaptado a su propio almacén tipo `produccion`.
- **RN-PRD-017** Producción evalúa la viabilidad técnica (costo real de
  insumos, tiempo de preparación, ajuste sugerido) de todo requerimiento
  de nuevo producto antes de que Comercial comprometa una fecha de
  lanzamiento (ver
  [ficha-requerimiento-nuevo-producto.md](../templates/comercial/ficha-requerimiento-nuevo-producto.md)).
  La misma evaluación aplica a mejoras continuas de receta impulsadas por
  I+D+i o Comercial.
- **RN-PRD-018** El costo real de una subreceta/producto aprovechable lo
  calcula el ERP automáticamente por orden de producción, nunca a mano:
  costo de insumos consumidos (el insumo completo comprado, no solo la
  parte aprovechable — ej. el tomate entero, no solo la pulpa) más costo
  de mano de obra (horas-hombre registradas × tarifa de producción). El
  desperdicio de cada insumo (tipo y peso) se registra por orden contra
  el desperdicio esperado de la receta (`receta_item.merma_pct`) — toda
  desviación relevante queda visible, no oculta en el costo promedio.
- **RN-PRD-019** Un insumo que el cliente pidió quitar (resta, RN-COM-028)
  **no se descuenta** del almacén de la sucursal al confirmarse la venta, y
  tampoco se repone al anularla: nunca salió. Cada tramo del producto
  configurado —tamaño, combinación, extras— aporta **su propia receta** y el
  consumo del plato es la suma de todas menos las restas; el empaque se
  suma aparte, según la modalidad (RN-EMP-003), porque no es parte de la
  receta.

## Fecha de vencimiento

- **RN-VNC-001** La fecha de vencimiento de un producto elaborado en
  cocina de producción se determina según normativa vigente y análisis de
  laboratorio propio del producto resultante.
- **RN-VNC-002** La fecha de vencimiento de un producto comprado a
  proveedor es la declarada por el proveedor.
- **RN-VNC-003** Un producto abierto/en uso en sucursal tiene vida útil
  adicional desde su apertura: hasta 7 días en refrigeración (~4°C
  promedio), o hasta 2 meses si está congelado a -18°C.
- **RN-VNC-004** Con cuánta anticipación se avisa que un lote está por
  vencer lo declara **cada artículo** (`articulo.dias_alerta_vencimiento`),
  no un número único para todo el almacén: la leche útil avisa con días y
  una conserva con meses, y un solo valor deja a uno de los dos avisando
  cuando ya no sirve. Un artículo sin ventana declarada no avisa.

## Código de barras / QR

- **RN-COD-001** No todo artículo cuenta con código de barras o QR; su
  ausencia no impide su gestión en el ERP (búsqueda por SKU o nombre
  comercial).
- **RN-COD-002** Los artículos producidos en cocina de producción se
  identifican con un QR que codifica SKU + Lote conjuntamente.

## Lote

- **RN-LOT-001** El código de lote lo asigna el ERP, siguiendo la
  nomenclatura definida por el área de Producción.
- **RN-LOT-002** Todo artículo producido se etiqueta con: cantidad, unidad
  de medida, código de barras/QR, número de lote, fecha de vencimiento, y
  condiciones de almacenamiento y transporte.
- **RN-LOT-003** El lote registra todas las variables documentadas durante
  el proceso de producción (incluyendo ajustes de receta flexible), para
  trazabilidad completa.
- **RN-LOT-004** Sacar un lote distinto del que FEFO sugiere exige un
  **motivo registrado** en el movimiento. Tomar el lote sugerido no es un
  override y no pide motivo: exigirlo siempre convierte el campo en un
  trámite que se llena con cualquier cosa, y un motivo que nadie escribe en
  serio da apariencia de control sin darlo.
- **RN-LOT-005** Una salida que el reparto FEFO no puede respaldar con
  ningún lote se registra igual —la operación ya ocurrió— y queda como
  movimiento sin lote, visible en el reporte de excepciones. Frenarla
  significaría negar una venta por un dato de trazabilidad que ya está mal.

## Unidad de medida

- **RN-UDM-001** Un artículo, receta o producto comercial solo admite una
  Unidad de Medida perteneciente a su propia Categoría de UdM; nunca de
  otra categoría.
- **RN-UDM-002** Cambiar la UdM de un artículo exige modificarla primero
  en las recetas que lo usan y luego en el artículo/producto comercial;
  genera un reporte de auditoría.
- **RN-UDM-003** Durante la transición de cambio de UdM, el artículo queda
  desactivado en recetas, requerimientos y ventas.
- **RN-UDM-004** La creación/edición de categorías de UdM y sus ratios es
  responsabilidad del área de compras y del área contable.

## Empaques

- **RN-EMP-001** La compra de empaque se planifica con anticipación: lead
  time típico mayor a 15 días entre cotización aceptada y recepción.
- **RN-EMP-002** Un empaque solo se vende directo al cliente en POS
  operado por trabajador; no está disponible en kiosko ni web.
- **RN-EMP-003** El consumo de empaque en una venta depende de la
  configuración del producto comercial (`empaque_id` + modalidades mesa/
  takeout/delivery marcadas); no se incluye en la receta.
- **RN-EMP-004** El empaque consumido junto a una venta no aparece en el
  comprobante, salvo que se venda como producto comercial independiente.

## Categoría

- **RN-CAT-001** Una categoría se crea a nivel empresa (no a nivel grupo
  empresarial); requiere participación del área de compras y del área
  contable.
- **RN-CAT-002** El asiento contable ligado a una categoría es
  configurable por tipo de movimiento (compra, consumo, merma, etc.), no
  una cuenta fija única.
- **RN-CAT-003** Asignar categoría a un artículo o activo es opcional; se
  recomienda por orden del catálogo.
- **RN-CAT-004** Una categoría puede eliminarse o renombrarse libremente
  (a diferencia del SKU, que nunca se elimina).

## Servicios

- **RN-SRV-001** El costeo de un servicio se calcula según su naturaleza
  (fórmula propia por tipo de servicio, ej. delivery: horas/hombre +
  desgaste de vehículo + combustible).
- **RN-SRV-002** El precio cobrado al cliente por un servicio = costeo +
  margen de contribución + % de cobertura de emergencias, definidos por el
  área comercial al cotizar.
- **RN-SRV-003** El delivery se cobra al cliente en tarifa según distancia,
  no en tarifa única.

## Almacén de transporte (estado `en_transito`)

- **RN-TRP-001** Los insumos en estado `en_transito` son inamovibles; no
  pueden cambiar de destino.
- **RN-TRP-002** Los productos en tránsito deben coincidir exactamente con
  los declarados en la guía de remisión.
- **RN-TRP-003** El almacén de transporte puede evolucionar de estado
  virtual a nodo físico (hub de tránsito) si la operación lo requiere; el
  modelo de almacenes debe soportar agregar nuevos tipos/nodos sin romper
  el diseño existente.

## Vehículo

- **RN-VEH-001** La adquisición de un vehículo la ve el área de compras,
  con aprobación de gerencia y del área contable/financiera.
- **RN-VEH-002** Un vehículo se asigna a un transportista o responsable,
  quien rinde cuentas del uso y de posibles daños o pérdidas.
- **RN-VEH-003** Un vehículo puede ser alquilado, o licenciado a un
  trabajador como beneficio laboral durante su estadía en la empresa.
- **RN-VEH-004** El registro de kilometraje de un vehículo da fe del buen
  uso y del cumplimiento de las rutas establecidas.

## Mantenimiento

- **RN-MNT-001** Cada activo (vehículo, equipamiento, local) tiene una
  frecuencia recomendada de mantenimiento.
- **RN-MNT-002** Un mantenimiento se programa y coordina con un
  proveedor de servicios.
- **RN-MNT-003** El mantenimiento puede adelantarse si el operador
  reporta desperfectos o baja de productividad del equipo.
- **RN-MNT-004** El reporte que adelanta un mantenimiento se dirige al
  área de compras y al área contable, para coordinar.

## Repuesto

- **RN-RPT-001** El stock mínimo de un repuesto se define según la
  frecuencia o urgencia de su uso, no con una regla única.
- **RN-RPT-002** Un repuesto debe tener número de serie o modelo
  compatible con el equipamiento/vehículo al que corresponde.
- **RN-RPT-003** La adquisición de un repuesto es responsabilidad del
  área de compras y del área de almacén.
- **RN-RPT-004** Un repuesto puede usarse para repotenciar un equipo
  degradado, aumentando su vida útil.

## Equipamiento

- **RN-EQP-001** El equipamiento tiene número de serie y se etiqueta,
  para facilitar el reporte de mantenimiento y el seguimiento en
  auditorías.
- **RN-EQP-002** El trabajador que usa un equipamiento debe recibir
  inducción de uso y reportar averías.
- **RN-EQP-003** Daños físicos, robo de piezas, sobrecarga o maltrato de
  un equipamiento son responsabilidad del trabajador que lo opera; según
  la gravedad, se eleva un reporte a RRHH, que notifica con memorándum o
  sanción.
- **RN-EQP-004** El equipamiento se audita de manera rutinaria.

## Almacén virtual de activos

- **RN-ACT-001** El almacén de activos solo permite la salida (venta o
  baja) de un activo depreciado en su totalidad, y únicamente con acta de
  autorización.
- **RN-ACT-002** La depreciación de un activo la controla el área contable
  de la empresa, no el almacén.

## Almacén de sucursal

- **RN-ALS-001** El stock de un SKU no puede exceder el máximo ni caer bajo
  el mínimo definidos para la jornada siguiente.
- **RN-ALS-002** El personal no puede vender, sustraer ni ingerir productos
  del sub-almacén.
- **RN-ALS-003** Personal no autorizado no puede conocer ni ingresar a las
  áreas de almacenamiento.
- **RN-ALS-004** Un producto dañado, en mal estado o vencido no puede
  mezclarse con productos buenos; se marca con etiqueta "NO USAR" y se
  entrega al repartidor en la siguiente entrega.
- **RN-ALS-005** Un traspaso de urgencia entre sub-almacenes de distinta
  empresa se subsana contablemente con factura de venta aprobada por el
  área contable del grupo en el cierre de mes.

## Cocina de producción

- **RN-CDP-001** Una cocina de producción nunca despacha a un almacén de
  sucursal directamente; solo entrega al almacén central.
- **RN-CDP-002** Ante posible plaga/invasión de animales, la cocina detiene
  su operación, solicita eliminación a la empresa operadora, y solo reanuda
  tras desinfección total de equipos y superficies.
- **RN-CDP-003** No puede ingresar personal sin elementos de bioseguridad.
- **RN-CDP-004** Toda devolución de SKUs sobrantes al almacén central exige
  guía de remisión.
- **RN-CDP-005** Todo equipo de frío (refrigeración/congelación) de la
  cocina de producción se verifica en rango de temperatura en el
  checklist de cada turno. Fuera de rango: los insumos/subrecetas
  comprometidos se marcan "NO USAR" (mismo criterio RN-ALS-004) y se
  trasladan a un equipo en buen estado si existe; se reporta de
  inmediato a Gerencia (mismo criterio que la falla de frío en apertura
  de sucursal, RN-SUC-009) y la producción no continúa en ese equipo
  hasta resolver.

## Almacén central

- **RN-ALM-001** No se saca ningún insumo del almacén sin guía.
- **RN-ALM-002** No se acepta un producto de proveedor dañado, en mal
  estado, o que no cumpla la ficha técnica/calidad establecida.
- **RN-ALM-003** No se acepta un producto de alta rotación con fecha de
  vencimiento menor a un mes.
- **RN-ALM-004** Los productos vencidos, dañados o devueltos por sucursales
  no pueden sustraerse; se desechan según el proceso establecido
  *(pendiente)*.
- **RN-ALM-005** Solo se reciben productos con guía y dentro del horario
  laboral; se cuentan y/o pesan antes de aceptar la carga.
- **RN-ALM-006** No se puede alquilar ni prestar espacio de almacén para
  productos no ingresados por la vía regular.
- **RN-ALM-007** El movimiento de inventario sigue política FEFO/FIFO.

## Inventario

- **RN-INV-001** No se despacha más de lo aprobado en la solicitud. Menos
  sí: si el abastecedor no tiene todo, despacha lo que hay y la diferencia
  queda en `solicitud_item.cantidad_despachada`.
- **RN-INV-002** No se recibe más de lo enviado sin registrar la diferencia
  (auditada). Al destino entra **lo que de verdad llegó**, no lo que decía
  la guía; la diferencia viaja en `inventory.transferencia_recibida`.
- **RN-INV-003** Una transferencia descuenta el origen al salir y suma el
  destino al recibirse; entre ambos momentos el stock está en tránsito.
- **RN-INV-004** Todo ajuste exige permiso `inventory.ajustar` y motivo.
- **RN-INV-005** Solo usuarios autorizados operan inventario; el acceso es
  configurable por rol en alcance (sucursal propia o toda la empresa),
  visibilidad (stock esperado visible u oculto/"a ciegas") y acción (solo
  conteo, conteo + requerimiento, solicitar ajuste, autorizar ajuste).
- **RN-INV-006** Solicitar un ajuste y autorizarlo son permisos distintos;
  no se auto-autoriza.
- **RN-INV-007** La periodicidad de conteos es configurable por el ERP y
  la determina **la categoría** a la que pertenece cada SKU, no un valor
  único de empresa ni de almacén: `diario`, `semanal`, `quincenal`,
  `mensual`, `semestral` o `anual` (`categoria.frecuencia_conteo`,
  ADR-019). Una categoría sin frecuencia queda fuera del conteo cíclico.
  La próxima fecha se cuenta desde el último conteo cerrado que cubrió esa
  categoría en ese almacén; un conteo general cubre a todas.
- **RN-INV-008** El stock mínimo (cubre un período de tiempo determinado)
  y el stock máximo (evita desborde de almacenamiento o pérdidas por
  rotación/vencimiento) de cada artículo los determinan las áreas de
  Producción, Contabilidad y Logística.
- **RN-INV-013** El punto de reorden se calcula como (demanda diaria ×
  tiempo de entrega en días) + stock de seguridad; por defecto, stock de
  seguridad = demanda diaria. Al alcanzarse, genera alerta de
  reabastecimiento (sucursal, central o producción).
- **RN-INV-014** Un conteo puede ser de rutina (programado) o parte de un
  proceso de ajuste/auditoría puntual. El conteo no corrige el stock: al
  cerrarse, cada diferencia genera un `ajuste` pendiente ligado a él
  (`ajuste.conteo_id`), que aprueba otro usuario (RN-INV-006). El stock
  esperado se congela al abrir el conteo, no al cerrarlo. Los ítems que
  nadie contó no generan ajuste — un conteo parcial no declara faltante lo
  que no se miró.
- **RN-INV-021** Si un conteo no se realiza en la fecha que su frecuencia
  exigía, se genera un reporte dirigido al área de almacén y a gerencia
  (evento `inventory.conteo_vencido`). El día en que vence todavía no es
  atraso; el reporte sale a partir del día siguiente.
- **RN-INV-022** Un almacén puede declarar un **abastecedor de respaldo**
  además del principal (ADR-040). Una solicitud que no nombra abastecedor va
  al principal, y **si el principal está dado de baja va al respaldo**: sin
  eso, dar de baja el central deja a la sucursal sin poder pedir nada. El
  respaldo tiene que ser de la misma empresa y **distinto del principal** —el
  día que el principal no esté, tampoco estaría él—. Una solicitud que **sí**
  nombra abastecedor no cae al respaldo: quien nombra un almacén está pidiendo
  a ese, y despachar desde otro en silencio es lo que el que recibe no puede
  notar hasta contar la mercadería. "No disponible" es estar dado de baja, no
  estar sin stock: el faltante tiene su propio camino (RN-INV-001/002).
- **RN-INV-023** El catálogo de artículos **se baja, se edita y se vuelve a
  subir** en el mismo formato, con revisión en el medio (ADR-051). La
  identidad de una fila es su `ID` o, si va vacío, su **código interno** — el
  nombre no sirve de clave porque el nombre es justamente lo que se corrige.
  La **unidad de medida de un artículo que ya existe no se cambia por
  planilla**: el stock, los movimientos y las recetas ya cargadas están
  expresados en la unidad actual, así que cambiarla no convierte nada,
  reinterpreta en silencio todo lo que ya existe; la fila se informa y no
  entra. Una categoría que el catálogo no reconoce **no frena la fila** —el
  artículo entra sin categoría— pero se muestra para que alguien la elija o
  la cree; el importador nunca la crea solo. Una celda vacía significa **no
  tocar**, no vaciar.
- **RN-INV-015** Un ajuste es válido, sin generar alarma, solo si está
  dentro de un margen de error definido por las áreas de almacén y
  contabilidad; fuera de ese margen dispara alarma/auditoría. El margen son
  **dos tolerancias que conviven** y basta cumplir una: un **porcentaje**
  sobre la cantidad esperada y un **piso en dinero** sobre la diferencia
  valorizada. El piso existe porque el porcentaje solo castiga a las
  categorías baratas, y una alerta que siempre suena es una alerta que
  nadie mira. Ambos valores viven en `inventory/margen_error_ajuste`
  (`parametro_empresa`, aprobado por Gerencia — RN-GER-009); el sistema los
  calcula, nunca los declara quien solicita el ajuste.
- **RN-INV-016** Un ajuste se origina por sobrante, faltante, merma/daño,
  o error de registro.
- **RN-INV-017** Toda merma se reporta en el módulo de producción o en el
  de inventario; debe estudiarse y rendir cuentas ante el almacén y el
  área contable. Mecanismo exacto de registro dentro de una auditoría
  *(pendiente)*.
- **RN-INV-018** Todo desperdicio se reporta en el módulo de producción;
  puede asociarse a una receta como producto derivado.
- **RN-INV-019** Toda devolución retorna el producto a su almacén de
  origen por una razón justificada (vencido, dañado, incumplimiento de
  plazo, ya no requerido, error al solicitar, duplicidad) y lo dirige a
  desecho, auditoría o reintegro a stock disponible. El destino solo aplica
  a lo que **vuelve** al almacén: lo que se le devuelve al proveedor se va,
  y su destino deja de ser problema nuestro. La devolución sucursal→central
  se ejecuta como transferencia, no como entidad aparte (ADR-028).
- **RN-INV-020** Toda devolución genera un reporte, dirigido al área de
  almacén (empresa→proveedor o sucursal→central) o al área comercial (si
  devuelve un cliente).
- **RN-INV-009** El stock disponible de un SKU en un almacén es su stock
  físico menos la suma de sus reservas activas. Comprometer stock nuevo
  (aprobar una solicitud) exige disponible suficiente; **consumir no se
  bloquea nunca por una reserva** — una venta o un consumo de producción
  ya ocurrieron y el ERP los registra igual, aunque el disponible quede
  negativo (ADR-020). Un disponible negativo es una promesa sin respaldo:
  hay que liberarla o reponer.
- **RN-INV-010** Al cancelarse o modificarse la solicitud/pedido que
  originó una reserva, el stock reservado vuelve a disponible
  automáticamente. Una solicitud ya despachada no se cancela: eso movió
  stock y se corrige recibiendo o devolviendo.
- **RN-INV-011** En el almacén central, un usuario autorizado puede
  liberar manualmente una reserva y redistribuirla entre otros
  solicitantes, ante desabastecimiento o sobredemanda del SKU.
- **RN-INV-012** El stock de merma o dañado es un subtipo de stock
  reservado: no apto para la actividad económica, pendiente de auditoría
  y desecho; se genera por devolución, rechazo de un almacén de sucursal,
  o auditoría de almacén. Apartarlo **no lo saca del almacén** —sigue en el
  estante y el conteo físico lo va a encontrar—; recién el desecho descuenta
  el stock y lo asienta como pérdida, y la auditoría puede reintegrarlo. Lo
  aparta quien lo detecta y lo resuelve otro (misma segregación que el
  ajuste, RN-INV-006).

## Compras

- **RN-CMP-001** Una OC emitida es inmutable; correcciones vía nueva versión o
  anulación.
- **RN-CMP-002** Se permiten recepciones parciales; no recibir más de lo
  ordenado sin permiso especial.
- **RN-CMP-003** La recepción actualiza el costo promedio del artículo.
- **RN-CMP-004** Una compra puede originarse en una cotización de
  proveedor; al recibir la respuesta, el borrador de la OC se actualiza
  con los precios unitarios cotizados.
- **RN-CMP-005** Toda compra debe estar sustentada con un comprobante de
  pago.
- **RN-CMP-006** Toda compra exige un egreso de dinero o un crédito con
  plazo determinado.
- **RN-CMP-007** Toda compra genera asientos contables y un movimiento de
  dinero.
- **RN-CMP-008** Una OC que supera el umbral de aprobación configurado
  (permiso `purchases.aprobar`) queda bloqueada para emisión hasta la
  aprobación del administrador/gerente; fraccionar una compra en varias OC
  menores para evadir el umbral está prohibido.
- **RN-CMP-009** Un proveedor nuevo requiere verificar RUC activo y habido
  en SUNAT antes del alta; sin alta no se emite ninguna OC a su nombre.
- **RN-CMP-010** Toda compra externa a proveedor ingresa por Almacén
  Central o por caja chica de compras; ninguna sucursal compra directo a un
  proveedor externo por su cuenta.
- **RN-CMP-011** Una compra a proveedor informal (sin capacidad de recibir
  OC) no lleva OC; se sustenta con boleta/factura y se paga con caja chica
  de compras.
- **RN-CMP-012** Con un proveedor clasificado preferente y de compra
  recurrente, la OC puede emitirse sin cotización comparativa nueva,
  sustentada con el requerimiento de almacén y la factura recibida.
- **RN-CMP-013** La caja chica de compras se rinde semanalmente a
  Contabilidad con comprobantes; sin rendición conciliada no se repone el
  fondo.
- **RN-CMP-014** El pago al proveedor lo ejecuta Contabilidad, no Compras;
  Compras sustenta el comprobante conforme y lo entrega a Contabilidad.
- **RN-CMP-015** La compra de un activo o equipamiento requiere cotización
  comparativa de mínimo 2 proveedores y validación de especificación y
  precio por el área solicitante y por gerencia antes de emitir la OC.
- **RN-CMP-016** El ERP calcula automáticamente el indicador de desempeño
  de cada proveedor (cumplimiento de plazo, conformidad en recepción,
  variación de precio) a partir de las recepciones registradas contra su
  OC.
- **RN-CMP-017** Un faltante no sustentado en la rendición de caja chica de
  compras genera reporte de Contabilidad a RRHH, identificando al
  responsable y el monto; tras derecho a descargo, RRHH emite memorándum y
  aplica el descuento por planilla del monto faltante (extiende
  RN-RRHH-007). Faltante reiterado (2+ veces) del mismo responsable puede
  escalar a carta de amonestación (RN-RRHH-004).

## Ventas

- **RN-COM-001** Confirmar una venta exige stock suficiente de los insumos de la
  receta (o política configurable de venta sin stock — por definir).
- **RN-COM-002** `idempotency_key` obligatoria (campo del body, no header —
  corregido 2026-07-26) al confirmar venta y al registrar pago; reintentos
  no duplican efectos.
- **RN-COM-003** El comprobante se encola al proveedor de facturación electrónica
  (Factiliza, ADR-005); una caída del proveedor no
  bloquea la venta.
- **RN-COM-004** Una venta de servicio, o generada por el área comercial,
  puede originarse en una cotización que el cliente acepta.
- **RN-COM-005** El flujo de una venta es: orden → envío del pedido a
  cocina → pago → emisión de comprobante. **Venta termina acá** (decisión
  2026-07-14) — preparación, emplatado/empaquetado, despacho y entrega al
  cliente pertenecen a `PROC-OPE-002` (Cumplimiento de pedido), que Venta
  dispara con `sales.venta_confirmada` sin esperar su resultado.
- **RN-COM-006** El pago puede realizarse por adelantado; el comprobante
  puede emitirse antes del pago (no recomendable).

- **RN-COM-007** La encuesta de satisfacción es selectiva: Marketing
  decide a qué cliente enviarla, nunca es automática para toda venta.
  Su disparador es `sales.venta_entregada`, emitido por `PROC-OPE-002`
  (Cumplimiento de pedido) — no ocurre dentro de Venta. Exige cliente
  identificado (`cliente_id` no nulo). Regla reactivada 2026-07-27 al
  definirse ese proceso; estuvo sin disparador desde 2026-07-14.

- **RN-COM-008** Datos del cliente son opcionales por defecto (nombre
  completo, DNI), salvo: takeout y delivery exigen teléfono + nombre de
  referencia; delivery exige además dirección exacta. Sin esos datos no
  se puede confirmar la venta en esas modalidades.
- **RN-COM-009** Antes de presentar el monto total, quien atiende (agente
  humano, IA o trabajador) debe repetir el pedido completo al cliente —
  control anti-error, aplica a los 3 canales (web queda exenta: el
  carrito ya es visual y editable por el propio cliente).
- **RN-COM-010** Ante desistimiento por producto sin stock/no disponible,
  se ofrecen alternativas antes de dar la venta por perdida.
- **RN-COM-011** Ante desistimiento por precio ("no conveniente"), se
  ofrecen opciones similares de menor precio o una promoción vigente
  antes de dar la venta por perdida (canal Central de Pedidos; aplica por
  extensión a los demás).
- **RN-COM-012** Ante desistimiento por tiempo de espera largo, se sugiere
  recojo en otra sucursal o cambiar delivery por recojo en sucursal antes
  de dar la venta por perdida.
- **RN-COM-013** El abandono de carrito/pedido se registra en cualquier
  canal y en cualquier paso (motivo si se conoce) — insumo para análisis
  de embudo/conversión, no solo para resolución en el momento.
- **RN-COM-014** Toda venta confirmada recibe un `numero_orden`
  correlativo, único por sucursal y día — es el número que ve el
  personal (cocina, mostrador, KDS); no se confunde con
  `idempotency_key` (técnico) ni con el correlativo del comprobante
  (fiscal, vía Factiliza). Aplica tenga o no `cotizacion_id` — toda venta
  confirmada ya es una Orden de Pedido (glosario) por sí misma.
- **RN-COM-015** La cuenta web de un cliente (`cliente.usuario_id`) es
  opcional y solo habilita autoservicio (ver historial, pedir online);
  nunca es requisito para comprar en sucursal o por Central de Pedidos
  — esas ventas enrutan al mismo `cliente` por sus datos (persona/
  contacto), sin necesidad de login.
- **RN-COM-016** Una venta puede cobrarse con más de un medio de pago
  (ej. mitad efectivo, mitad tarjeta) — confirmado 2026-07-20 como caso
  real del negocio. La suma de `pago.monto` de una venta debe igualar
  `venta.total` antes de que la venta pase a `estado=pagada`.
- **RN-COM-017** Un descuento manual sobre el total de una orden lo
  **autoriza un supervisor o encargado**, nunca el cajero que lo pide, y
  se registra con **motivo** (`cortesia`, `reclamo`, `colaborador`,
  `promocion`, `convenio`) y **quién lo autorizó**, porque debe poder
  explicarse en los reportes de descuentos. Solo se aplica a una venta en
  estado `orden`. No confundir con las **promociones**, que se definen a
  nivel de marca y sucursal, se activan solas cuando el pedido cumple sus
  condiciones (ej. segunda pizza a mitad de precio si el cliente pide dos
  del mismo tamaño, en los días en que la promoción está vigente,
  aplicando el descuento sobre el precio base de la más barata y sin
  incluir extras), y viven en un motor de reglas aparte (ver ADR-018 y
  `ROADMAP.md`).
- **RN-COM-018** Una orden puede **dividirse en varias cuentas**: el
  cajero selecciona qué productos cobra en ese momento y los no
  seleccionados quedan pendientes en la misma orden. Cada cuenta acumula
  sus propios pagos, puede tener un receptor distinto y **emite su propio
  comprobante**. La venta pasa a `estado=pagada` recién cuando ninguna
  cuenta queda con saldo. Si no se selecciona nada, se cobra la orden
  completa como una sola cuenta.

- **RN-COM-019** La **precuenta** es un documento **no fiscal**: no tiene
  serie ni correlativo, no se envía a SUNAT y no cambia el estado de la
  venta. Es el papel que el cliente pide para revisar su consumo antes de
  pagar. Se imprime tantas veces como haga falta y no se audita; el
  comprobante fiscal nace recién al cobrar.
- **RN-COM-020** Antes de enviar a cocina, corregir el pedido no toca el
  servidor: vive en el punto de venta. Después de enviarlo, **quitar líneas
  requiere autorización de supervisor y motivo**, porque la comanda ya salió
  y el insumo ya se descontó — anularlas repone stock. Una línea ya cobrada
  no se quita por esta vía: eso es nota de crédito. Quitar todas equivale a
  anular la orden.
- **RN-COM-021** Un **extra** (extra queso, doble carne) es un producto
  comercial con **su propia receta**, que se ejecuta en la sucursal y se
  suma a la del producto al que se agrega. Solo se ofrece dentro de un
  producto que lo admita, nunca suelto en la carta. Al venderse es una línea
  propia colgada de la del plato, y **hereda su cuenta**: dividir la cuenta
  no puede dejar la pizza en una y su extra en otra. Su consumo se
  multiplica por el plato — dos pizzas con extra queso llevan dos porciones.
- **RN-COM-022** Un producto comercial puede venderse **por variante**:
  "Pizza Peperoni Personal / Mediana / Familiar" son productos hijos del
  mismo padre, cada uno con **su propia receta y su propio precio completo**
  —no un recargo sobre un precio base—. El padre agrupa y **no se vende**:
  no tiene receta ni admite precio, y en el punto de venta elegir una
  variante es **obligatorio**. Las variantes no aparecen sueltas en la carta
  y no admiten variantes propias (un solo nivel). La tarjeta del padre
  muestra el precio de la variante más barata como "desde".
- **RN-COM-023** Los extras de un producto pueden organizarse en **grupos**
  ("Salsas", "Toppings"), y cada grupo declara **cuántas opciones hay que
  elegir**: mínimo 1 lo vuelve obligatorio y bloquea el pedido hasta que se
  elija; mínimo 0 lo deja opcional. El máximo del grupo limita **opciones
  distintas**, no unidades de una misma (RN-COM-021 ya limita eso). Un extra
  sin grupo es siempre opcional. La regla se hace cumplir al confirmar la
  venta, no solo en la pantalla: el kiosko y la central de pedidos entran
  por el mismo endpoint.
- **RN-COM-024** Toda **cantidad de una línea de receta** puede escribirse
  como operación aritmética ("1000/3", "250*1.5"). Se guarda **el
  resultado**, redondeado a los decimales de la unidad de medida del insumo
  (RN-GER-010, RN-UDM-001), junto con la expresión tecleada para poder
  reeditarla. La expresión no se recalcula sola: la verdad es la cantidad
  guardada. Duplicar una receta la clona con el sufijo "(copy)" y sin
  destino asignado; escalarla por un factor redondea **cada línea con su
  propia unidad** (1.5 bollos de masa son 2, no 1.5).
- **RN-COM-025** La **comida del personal** —la que el negocio da en fines
  de semana, feriados o días de alta actividad— se registra como una orden
  de tipo `consumo_personal`: se prepara y se despacha como cualquier
  pedido (comanda, KDS, entrega), pero **todas sus líneas valen cero**, no
  se cobra y **no emite comprobante**. No es un descuento del 100% sobre
  una venta: una venta de S/ 0.00 declararía un ingreso que no existe y
  emitiría un comprobante que no corresponde (ADR-034).
- **RN-COM-026** Cada consumo de personal lo **autoriza un encargado con su
  PIN** —permiso `sales.registrar_consumo_personal`, separado de
  `sales.crear`— y se registra con **motivo** (`fin_semana`, `feriado`,
  `alta_actividad`, `capacitacion`, `otro`). Sin motivo no hay con qué
  explicar el gasto, y sin firma cualquiera se sirve gratis. El acto queda
  en `audit_log` (RN-AUD-005).
- **RN-COM-027** El costo del consumo de personal **sale del inventario
  como `consumo_interno`** —no como `consumo_venta`— y se reconoce
  valorizado a costo promedio como **gasto de alimentación de personal**,
  no como costo de ventas. La orden queda en estado `cerrada` al
  entregarse: es su único cierre posible, porque nunca pasa por caja.
  Anularla repone el insumo y **reversa el asiento**.
- **RN-COM-028** Una línea de venta puede llevar **restas**: insumos de la
  receta que ese plato NO lleva ("sin cebolla"). Es el último tramo del
  orden de modificadores (RN-PRD-004). Lo que se puede quitar **es** lo que
  la receta del producto pone —no hay una lista aparte que mantener— y
  pedir quitar algo que la receta no usa se rechaza al confirmar la venta.
  Una resta **no cambia el precio** de la línea, pero **sí** el consumo: el
  insumo quitado no se descuenta del almacén (RN-PRD-019), y la reposición
  por anulación o nota de crédito devuelve solo lo que se consumió. Las
  restas viajan a cocina como parte del pedido (KDS y comanda), no como
  texto libre en la nota.
- **RN-COM-029** Una orden ya enviada a cocina **sigue viva mientras no se
  cobre**: admite líneas nuevas y admite que se le quiten.
  - **Agregar no requiere autorización de nadie** y usa el mismo permiso que
    crear la orden. Una mesa pide de a poco, y obligar a abrir una orden
    nueva para la segunda ronda termina en dos cuentas y dos entregas para
    la misma mesa.
  - **Quitar** —una línea o la orden entera— es gratis **dentro de los 5
    minutos** de haber salido a cocina: ahí es corregir un tecleo, el plato
    todavía no se armó y nadie tuvo tiempo de aprovecharlo. **Pasada esa
    ventana** lo autoriza un supervisor con su PIN en el mismo terminal
    (RN-COM-020), porque el insumo ya se usó de verdad y reponerlo es plata
    que sale del inventario.
  - La ventana de la **orden** se mide contra su **última línea**, no contra
    su creación: una mesa que sigue pidiendo tiene la orden abierta desde
    hace una hora, pero lo último que mandó puede ser de hace un minuto.
  - Quitar un lote de líneas exige firma si **alguna** salió de la ventana:
    de lo contrario, acompañar una línea vieja con una recién agregada sería
    la forma de quitarla sin que nadie firme.
  - Después del cobro la cuenta está cerrada: lo que venga es otra orden, y
    deshacer lo cobrado es nota de crédito (RN-CPP-009).
- **RN-COM-030** El **tipo de una receta se deriva, no se declara**: la que
  produce un artículo es una **subreceta** —se guarda para usarla en otra— y
  la que no, es un **producto de venta**. Guardarlo en una columna aparte
  sería un segundo lugar donde puede estar mal. La categoría por la que se
  filtra es la del artículo que la receta produce, así que solo alcanza a
  las subrecetas.
- **RN-COM-031** El recetario **se baja, se edita y se vuelve a subir**, y la
  carga es en **dos pasos con revisión en el medio**: primero se dice qué
  entra y qué no **sin guardar nada**, y recién después de que alguien lo
  mira se importa. Un insumo que el catálogo no reconoce no cancela la carga:
  se elige cuál es, **se crea desde el mismo diálogo**, o se omite esa línea
  **a la vista** — nunca en silencio, y nunca creado solo por el importador
  (ADR-046). Una fila con la columna `ID` llena **actualiza** esa receta en
  vez de crear otra; una sin `ID` cuyo nombre ya existe se informa y **no
  arrastra a las demás**. Al actualizar, los ingredientes que el archivo no
  menciona **se conservan** salvo que se pida quitarlos **receta por receta**,
  viendo antes cuántas líneas se pierden: subir una hoja parcial por error no
  puede vaciar una receta (ADR-051). Lo que la pantalla devuelve se revalida
  en el servidor: es un dato que el cliente pudo editar.

## Cumplimiento de pedido

Proceso `PROC-OPE-002` ([workflows.md](workflows.md#cumplimiento-de-pedido)),
área dueña Operaciones. Empieza donde termina Venta (RN-COM-005) y cubre
preparación, despacho y entrega en las tres modalidades.

- **RN-CUP-001** El cumplimiento arranca con la venta ya confirmada: el
  KDS muestra la Orden de Pedido, nunca el Carrito (RN-CAR-002 decide si
  el pedido llega antes o después del pago, según el punto de venta).
- **RN-CUP-002** El avance de un ítem es estrictamente secuencial y sin
  retroceso: `pendiente → en_preparacion → listo → entregado`. No se
  salta ni se revierte un estado; una corrección se registra como
  incidencia, no reescribiendo el avance.
- **RN-CUP-003** El estado de preparación es único por ítem de venta y es
  la fuente de verdad del avance. Una pantalla KDS es un filtro sobre ese
  estado, nunca una copia — dos pantallas jamás muestran avances distintos
  del mismo ítem.
- **RN-CUP-004** Ningún pedido se entrega sin verificar el pedido completo
  contra la comanda: control de salida obligatorio, responsabilidad de
  quien despacha.
- **RN-CUP-005** Un pedido solo se entrega cuando todos sus ítems están
  al menos `listo`. La entrega es un acto único por venta e idempotente:
  repetirla no vuelve a emitir el evento ni duplica efectos.
- **RN-CUP-006** La entrega la registra un trabajador con permiso de
  entrega, distinto del avance de cocina, y queda auditada (quién, cuándo).
- **RN-CUP-007** En delivery se registra siempre quién entrega:
  repartidor propio o repartidor de plataforma externa — este último sin
  vínculo laboral ni gestión como recurso propio (RN-PER-003).
- **RN-CUP-008** Una entrega fallida (cliente ausente, dirección errada,
  rechazo en la puerta) se registra con motivo y **no** marca el pedido
  como entregado; el encargado de tienda decide devolución, nuevo intento
  o merma. Un pedido no entregado nunca se cierra en silencio.
- **RN-CUP-009** En mesa, el servicio se considera terminado con la
  entrega del último pedido de esa atención; recién ahí queda habilitado
  el cobro al finalizar el consumo (RN-POS-005).
- **RN-CUP-010** Un producto rechazado por el cliente en la entrega se
  reprocesa o se devuelve, con motivo registrado; si se desecha, genera
  merma (RN-INV-017).
- **RN-CUP-011** Un pedido de takeout no recogido espera el plazo que
  defina la sucursal; vencido el plazo se escala al encargado, que decide
  resguardo, merma o anulación con devolución del dinero al cliente.
- **RN-CUP-012** Una venta ya entregada no se anula por la vía de
  anulación de orden (reservada a la orden no pagada): requiere nota de
  crédito y, si corresponde, devolución — RN-GEN-002. La anulación
  temprana coordinada con la sucursal sigue el límite de la Central de
  Pedidos (5 minutos desde la emisión del pedido).
- **RN-CUP-013** La cocina de una sucursal se configura como una **cadena
  de estaciones** ordenadas (armado → horno → …). Cada línea del pedido
  recorre las estaciones que atienden su categoría, de la primera a la
  última: marcarla en una estación intermedia la manda a la siguiente, y
  solo queda `listo` cuando ya no le queda ninguna por delante — una
  bebida cuya categoría no atiende el horno se lo salta sin configurar
  nada. La pantalla de despacho no prepara ni marca: muestra el pedido
  completo, cuántas líneas van y **en qué estación está cada una**, para
  saber por quién se espera antes de entregarlo (RN-CUP-005).
- **RN-CUP-014** Un extra (el sabor de una pizza, el queso adicional) **no
  es un plato aparte en cocina**: se muestra dentro del plato del que
  cuelga, recorre las estaciones que le tocan a ese plato, se marca cuando
  se marca el plato y se anula cuando se anula el plato — reponiendo lo que
  consumió. Sigue siendo una línea propia de la venta porque tiene su
  receta, su precio y su rastro (RN-COM-021); lo que no tiene es avance
  propio. Mostrarlo suelto hacía que la comanda y la pantalla dijeran "una
  pizza" y "un peperoni" como si fueran dos preparaciones.

## Comercial — estrategia

- **RN-CML-001** Ningún precio se publica sin calcular su margen de
  contribución (precio − costo variable); si queda bajo el mínimo objetivo
  u otro de referencia, requiere justificación escrita y aprobación de
  gerencia (extiende RN-PRC-001/002).
- **RN-CML-002** Toda oferta o promoción exige un brief con objetivo único,
  mecánica, fecha de fin y margen calculado, aprobado por Comercial y
  Contabilidad, antes de publicarse en cualquier canal (extiende
  RN-PRM-001).
- **RN-CML-003** Todo criterio de incentivo o comisión por cumplimiento de
  meta de venta se define y aprueba entre Comercial, RRHH y gerencia, se
  documenta y comunica al personal antes de aplicarse; nunca con efecto
  retroactivo.
- **RN-CML-004** La evaluación de desempeño comercial del personal de
  atención al cliente es continua y la ejecuta Comercial; alimenta como
  insumo la evaluación de personal que gestiona RRHH, sin sustituir la
  decisión de continuidad laboral, que sigue siendo de RRHH/administración.
- **RN-CML-005** Ninguna iniciativa de producto nuevo se compromete con un
  cliente o canal antes de validar su viabilidad (receta, costo, tiempo de
  preparación) con Producción/I+D+i.
- **RN-CML-006** Una decisión de precio, canal o producto basada en
  investigación de mercado requiere el hallazgo documentado (pregunta,
  fuente, fecha) — sin esto, se registra como apuesta, no como decisión
  basada en datos.

## Marketing

- **RN-MKT-001** Marketing **gestiona las marcas** del grupo: su buen uso,
  consistencia, contenido, campañas y naming. Aplica los lineamientos de
  identidad (RN-MAR-003) sin una capa de aprobación extra para el trabajo
  de marca cotidiano. Solo las decisiones **reservadas a la sociedad**
  —modificación estructural de la identidad de una marca o cesión/venta de
  propiedad intelectual (RN-MAR-004, RN-GRP-006)— exceden a Marketing y
  las deciden los socios/holding.
- **RN-MKT-002** Todo contenido publicado responde a la marca y su público
  objetivo, no solo a la viralidad; contenido que gana alcance a costa de
  la coherencia de marca no se publica.
- **RN-MKT-003** Toda campaña tiene un **brief aprobado** antes de salir a
  canal (objetivo, público, canal, mensaje, presupuesto, KPI). La campaña
  de impulso de venta define su objetivo comercial con Comercial:
  **Marketing atrae el lead, Comercial cierra la venta e investiga la
  oportunidad**; la conversión se mide contra la venta real en el ERP.
- **RN-MKT-004** El **material** promocional (bien) lo especifica y valida
  Marketing, pero su compra pasa por el flujo de Compras (OC o caja chica
  según monto, RN-CMP-*); Marketing no compra por fuera. La **agencia**
  (servicio) no pasa por Compras — ver RN-MKT-006.
- **RN-MKT-005** Toda sucursal debe quedar **correctamente implementada**
  con el material vigente —producto nuevo y clásico—; Marketing verifica
  la implementación en sucursal, no basta con enviar el material.
- **RN-MKT-006** La evaluación de una propuesta de agencia externa (o de la
  alternativa interna) la realiza **Marketing**, por su conocimiento del
  servicio, contra el objetivo y el presupuesto; **Gerencia valida** la
  decisión. La agencia (servicio) no pasa por la evaluación de Compras: se
  formaliza por contrato (RN-CTR-002/003) y el pago lo ejecuta Contabilidad
  (RN-CPP-006).
- **RN-MKT-007** El naming de un producto o campaña lo define/valida
  Marketing, asegurando disponibilidad, coherencia con la marca y ausencia
  de conflicto (verificación de registro/legal si aplica).

## Contabilidad

- **RN-CTB-001** Todo asiento cuadra: suma debe = suma haber.
- **RN-CTB-002** Los asientos de un periodo cerrado son inmutables; correcciones
  por asiento inverso.
- **RN-CTB-003** La contabilidad refleja los eventos operativos, no los sustituye.
- **RN-CTB-004** El área concentra hoy tesorería, finanzas y registro en un solo
  responsable; se acepta el riesgo de falta de segregación de forma explícita y
  se compensa con supervisión de Gerencia (aprobación de egresos, arqueos
  sorpresa, visto de conciliaciones y cierres). Ver
  [política de Contabilidad](../contabilidad/politica-contabilidad.md).
- **RN-CTB-005** Todo egreso que supere el umbral configurado requiere
  aprobación previa de Gerencia antes de ejecutarse; el pago sin aprobación no
  puede ejecutarse en el ERP.
- **RN-CTB-006** El cierre de un periodo contable exige la conciliación
  bancaria del periodo revisada y visada por Gerencia; sin conciliación visada
  no cierra el periodo.
- **RN-CTB-007** Todo faltante o sobrante detectado en un arqueo se documenta en
  acta, se atribuye al responsable (mismo criterio de descuadre que el cierre de
  caja) y notifica a RRHH cuando corresponde.
- **RN-CTB-008** Un mismo comprobante no se paga dos veces; el ERP bloquea el
  doble pago (idempotencia). El pago a proveedor solo procede con comprobante
  conforme entregado por Compras (RN-CMP-014).
- **RN-CTB-009** Contabilidad ejerce auditoría interna sobre las áreas
  operativas aguas arriba (Compras, Almacén, cajas de sucursal); **no se audita
  a sí misma**: su tesorería (depósitos, pagos, conciliación, custodia propia)
  la audita Gerencia. Toda auditoría/arqueo la ejecuta quien **no custodia** el
  fondo o dato revisado; el custodio está presente como testigo, no cuenta por
  el auditor.
- **RN-CTB-010** Ningún asiento se registra fuera de un periodo contable
  abierto; un asiento manual sobre un periodo sin abrir o ya cerrado se
  rechaza (409).
- **RN-CTB-011** La generación automática de asientos usa el mapeo
  configurable evento→cuentas (`regla_asiento`) por empresa; si la empresa no
  configuró mapeo para un evento, el asiento se omite (se audita en el log)
  — nunca bloquea el proceso operativo que lo originó (mismo criterio de
  módulos operativos con dependencias sin configurar, ej. inventory).

## Emisión y distribución de reportes (módulo reports, ADR-033)

Reglas de **quién recibe qué**, no de qué dice cada reporte. Lo que un
reporte contiene es del módulo dueño del hecho; lo que estas reglas gobiernan
es a dónde va y quién puede abrirlo.

- **RN-REP-001** El catálogo de emisiones es cerrado y vive en código. Una
  regla de distribución solo puede referirse a un `codigo_emision` existente;
  el cliente nunca aporta tablas, columnas ni filtros que compongan una
  consulta. Mismo criterio que ADR-024 para la consulta, aplicado a la
  emisión.
- **RN-REP-002** Leer un reporte emitido exige **las dos** puertas: ser
  destinatario (o tener `reports.leer_todo`) **y** tener el permiso que la
  emisión declara, que es el de su módulo dueño. Estar en la lista de
  distribución no otorga acceso al dato: un cocinero puede enterarse de que
  hubo un descuadre de caja sin ver el detalle de la caja.
- **RN-REP-003** Solo se persisten los campos que la emisión declara. Un
  payload que traiga de más no se filtra al cliente por olvido de nadie.
- **RN-REP-004** Las entregas no son retroactivas: `reporte_emitido.regla_id`
  y `entrega_reporte.motivo` se congelan al emitir. Cambiar la regla mañana no
  reescribe a quién le llegó ayer — mismo criterio que la alerta de pedido
  demorado, que guarda el umbral vigente al alertar.
- **RN-REP-005** Una emisión sin destinatarios **se persiste igual**, con cero
  entregas, y aparece como hueco en la matriz de distribución. Un aviso que no
  llegó a nadie es información de gestión, no un no-evento.
- **RN-REP-006** Un área, una regla y sus destinatarios pertenecen a una
  empresa. Un usuario destinatario debe pertenecer a la empresa de la regla.
- **RN-REP-007** Toda alta, cambio o baja de área, miembro, regla o
  destinatario deja rastro en `audit_log` (ADR-031). El gobierno de la
  distribución es auditable por definición: cambiar a quién le llega un
  descuadre es un acto de autoridad.
- **RN-REP-008** Una regla por (empresa, emisión, sucursal). La regla sin
  sucursal es la general de la empresa y **solo aplica donde no hay una
  específica** — si aplicaran las dos, quien esté en ambas recibiría el mismo
  hecho dos veces.
- **RN-REP-009** Todo reporte dice **quién provocó el hecho**. Cuando lo
  detecta el sistema —un barrido, un cruce de umbral— el actor queda nulo y se
  muestra como «Sistema»: inventarle una persona a un hecho que nadie provocó
  convierte un aviso de proceso en una acusación. Los reportes anteriores a
  ADR-036 dicen «Sistema» porque el dato nunca se guardó; no se rellenan hacia
  atrás.
- **RN-REP-010** Toda emisión que declara `referencia_tipo` tiene un destino
  montado: un endpoint real donde se mira —y se resuelve— el hecho. Un reporte
  que informa y no lleva a ninguna parte deja al lector saliendo a buscar el
  registro a mano, que es lo que el reporte venía a evitar. Lo congela
  `tests/test_destinos.py` contra las rutas realmente montadas.
- **RN-REP-011** Un escalamiento ancla a un `reporte_emitido` **con empresa**.
  Un hecho que no se pudo atribuir a una empresa no tiene área a la que
  elevarse ni permiso de módulo que lo cubra.
- **RN-REP-012** La cadena sube **de a un escalón** (supervisor → comercial →
  gerencia) y su historial es **append-only**: cada nivel agrega qué hizo, y
  ninguno reescribe lo que dijo el anterior. Saltarse un nivel o pisar su
  entrada deja el registro como la versión del último que pasó, y ese registro
  es el insumo de la mejora continua.
- **RN-REP-013** Un reporte tiene **una sola cadena abierta** a la vez. Dos
  cadenas sobre el mismo hecho dan dos verdades y dos responsables. Una cadena
  terminada libera el reporte: un problema que vuelve a pasar se escala de
  nuevo, y que aparezca dos veces es justamente lo que hay que poder ver.
- **RN-REP-014** Abrir, accionar, elevar y resolver un escalamiento dejan
  rastro en `audit_log` (ADR-031), por lo mismo que RN-REP-007: decidir que
  algo sube de nivel —o que se da por resuelto— es un acto de autoridad.

> Nota: esta lista crece con cada módulo. Al implementar un módulo se agregan
> aquí sus reglas antes de codificarlas.
