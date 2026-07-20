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
  encargado de sucursal.

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
  cajero → encargado de tienda/supervisor (al cierre de caja, tras
  confirmar valores) → área contable (verifica y pone a disposición de la
  empresa). En la apertura de caja la cadena se recorre en sentido
  inverso: área contable/encargado de tienda/supervisor → cajero. Cada
  relevo, en cualquier sentido, exige que quien recibe se autentique con
  usuario y PIN en el ERP y confirme que los valores son correctos.
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
  bancarios, o un contrato que autoriza un crédito.
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
  estado civil, religión — Ley 26772).
- **RN-RRHH-014** El uniforme y EPP son condición de trabajo: se entregan y
  devuelven con acta firmada, y su movimiento se registra en el ERP como
  artículo de almacén.

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

## Fecha de vencimiento

- **RN-VNC-001** La fecha de vencimiento de un producto elaborado en
  cocina de producción se determina según normativa vigente y análisis de
  laboratorio propio del producto resultante.
- **RN-VNC-002** La fecha de vencimiento de un producto comprado a
  proveedor es la declarada por el proveedor.
- **RN-VNC-003** Un producto abierto/en uso en sucursal tiene vida útil
  adicional desde su apertura: hasta 7 días en refrigeración (~4°C
  promedio), o hasta 2 meses si está congelado a -18°C.

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

- **RN-INV-001** No se despacha más de lo aprobado en la solicitud.
- **RN-INV-002** No se recibe más de lo enviado sin registrar la diferencia
  (auditada).
- **RN-INV-003** Una transferencia descuenta el origen al salir y suma el
  destino al recibirse; entre ambos momentos el stock está en tránsito.
- **RN-INV-004** Todo ajuste exige permiso `inventory.ajustar` y motivo.
- **RN-INV-005** Solo usuarios autorizados operan inventario; el acceso es
  configurable por rol en alcance (sucursal propia o toda la empresa),
  visibilidad (stock esperado visible u oculto/"a ciegas") y acción (solo
  conteo, conteo + requerimiento, solicitar ajuste, autorizar ajuste).
- **RN-INV-006** Solicitar un ajuste y autorizarlo son permisos distintos;
  no se auto-autoriza.
- **RN-INV-007** La periodicidad de conteos es configurable por el ERP.
- **RN-INV-008** El stock mínimo (cubre un período de tiempo determinado)
  y el stock máximo (evita desborde de almacenamiento o pérdidas por
  rotación/vencimiento) de cada artículo los determinan las áreas de
  Producción, Contabilidad y Logística.
- **RN-INV-013** El punto de reorden se calcula como (demanda diaria ×
  tiempo de entrega en días) + stock de seguridad; por defecto, stock de
  seguridad = demanda diaria. Al alcanzarse, genera alerta de
  reabastecimiento (sucursal, central o producción).
- **RN-INV-014** Un conteo puede ser de rutina (programado) o parte de un
  proceso de ajuste/auditoría puntual.
- **RN-INV-015** Un ajuste es válido, sin generar alarma, solo si está
  dentro de un margen de error definido por las áreas de almacén y
  contabilidad; fuera de ese margen dispara alarma/auditoría.
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
  desecho, auditoría o reintegro a stock disponible.
- **RN-INV-020** Toda devolución genera un reporte, dirigido al área de
  almacén (empresa→proveedor o sucursal→central) o al área comercial (si
  devuelve un cliente).
- **RN-INV-009** El stock disponible de un SKU en un almacén es su stock
  físico menos la suma de sus reservas activas.
- **RN-INV-010** Al cancelarse o modificarse la solicitud/pedido que
  originó una reserva, el stock reservado vuelve a disponible
  automáticamente.
- **RN-INV-011** En el almacén central, un usuario autorizado puede
  liberar manualmente una reserva y redistribuirla entre otros
  solicitantes, ante desabastecimiento o sobredemanda del SKU.
- **RN-INV-012** El stock de merma o dañado es un subtipo de stock
  reservado: no apto para la actividad económica, pendiente de auditoría
  y desecho; se genera por devolución, rechazo de un almacén de sucursal,
  o auditoría de almacén.

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
- **RN-COM-002** `Idempotency-Key` obligatoria al confirmar venta y al registrar
  pago; reintentos no duplican efectos.
- **RN-COM-003** El comprobante se encola a Nubefact; una caída del proveedor no
  bloquea la venta.
- **RN-COM-004** Una venta de servicio, o generada por el área comercial,
  puede originarse en una cotización que el cliente acepta.
- **RN-COM-005** El flujo de una venta es: orden → envío del pedido a
  cocina → pago → emisión de comprobante. **Venta termina acá** (decisión
  2026-07-14) — preparación, emplatado/empaquetado, despacho y entrega al
  cliente son proceso(s) posterior(es), aún sin definir.
- **RN-COM-006** El pago puede realizarse por adelantado; el comprobante
  puede emitirse antes del pago (no recomendable).

> ⚠ **RN-COM-007 (pendiente, fuera de alcance de Venta)** — la regla de
> encuesta de satisfacción (marketing selecciona cliente tras la entrega)
> sigue siendo válida como intención de negocio, pero su disparador
> (entrega al cliente) ya no ocurre dentro de Venta — depende del/los
> proceso(s) de cumplimiento de pedido sin definir. No renumerar: se
> retoma cuando ese proceso se modele.

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
  (fiscal, vía Nubefact). Aplica tenga o no `cotizacion_id` — toda venta
  confirmada ya es una Orden de Pedido (glosario) por sí misma.
- **RN-COM-015** La cuenta web de un cliente (`cliente.usuario_id`) es
  opcional y solo habilita autoservicio (ver historial, pedir online);
  nunca es requisito para comprar en sucursal o por Central de Pedidos
  — esas ventas enrutan al mismo `cliente` por sus datos (persona/
  contacto), sin necesidad de login.

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

## Contabilidad

- **RN-CTB-001** Todo asiento cuadra: suma debe = suma haber.
- **RN-CTB-002** Los asientos de un periodo cerrado son inmutables; correcciones
  por asiento inverso.
- **RN-CTB-003** La contabilidad refleja los eventos operativos, no los sustituye.

> Nota: esta lista crece con cada módulo. Al implementar un módulo se agregan
> aquí sus reglas antes de codificarlas.
