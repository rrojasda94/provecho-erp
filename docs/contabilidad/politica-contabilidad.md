# Política de Contabilidad — Grupo Majambo

Reglas de gobierno del área que registra, controla y mueve el dinero. Aplica a
las tres funciones (tesorería, finanzas, contabilidad-registro) mientras las
ejecute una sola área.

## Segregación de funciones y supervisión

**El problema de control.** La buena práctica contable separa a quien **mueve**
el dinero (tesorería: paga, cobra, custodia) de quien lo **registra**
(contabilidad: asienta, concilia, cierra). Cuando la misma persona hace ambas,
un error o un desvío puede quedar oculto porque no hay un segundo par de ojos
independiente.

**La decisión (2026-07).** A la escala actual del grupo (microempresa REMYPE,
ver [área RRHH](../rrhh/README.md)) no hay personal para separar las funciones.
Se acepta el riesgo de forma **explícita** y se compensa con controles de
Gerencia. Esto es una decisión de negocio consciente, no un descuido.

**Controles compensatorios de Gerencia** (reemplazan la separación ausente):

1. **Aprobación de egresos sobre umbral** — todo pago que supere el umbral
   definido lo autoriza Gerencia **antes** de ejecutarse (RN-CTB-005). El
   umbral vive en configuración, no en el código.
2. **Arqueo sorpresa** — Gerencia (o quien delegue) cuenta caja y fondos sin
   aviso previo, con acta firmada (PROC-CTB-005). Es el control que más
   disuade el desvío de efectivo.
3. **Revisión de conciliaciones** — Gerencia revisa y visa la conciliación
   bancaria periódica; una conciliación sin visar no cierra el periodo.
4. **Doble mirada en el cierre** — el cierre de periodo lo prepara Contabilidad
   y lo aprueba Gerencia; periodo cerrado es inmutable (RN-CTB-002).
5. **Trazabilidad total** — cada movimiento, relevo y ajuste queda en el ERP
   con usuario + PIN y valor anterior/nuevo (auditoría innegociable del
   proyecto). El rastro es el sustituto técnico de la separación.

**Ruta de upgrade.** Cuando el volumen lo justifique (más sucursales, más
personal administrativo, salida del régimen REMYPE ~2027), se separa la
función de **tesorería** (caja, pagos, custodia) de la de **registro**
(asientos, conciliación, cierre) en dos responsables distintos. La supervisión
de Gerencia se mantiene sobre ambas. No requiere reescribir procesos: los SOPs
ya distinguen por función (grupos `Tesoreria/`, `Finanzas/`, `Cierre/`).

## Principios de registro

- **RN-CTB-001 — Partida doble.** Todo asiento cuadra: suma debe = suma haber.
- **RN-CTB-002 — Inmutabilidad del periodo.** Los asientos de un periodo
  cerrado no se editan; se corrigen con asiento inverso.
- **RN-CTB-003 — Reflejo, no sustitución.** La contabilidad registra los
  eventos operativos; no crea la operación.
- **Sin eliminación física** — nada se borra; se reversa. Coherente con la
  auditoría del proyecto.

## Principios de tesorería

- **RN-CTB-005 — Aprobación de egresos.** Pago sobre umbral requiere
  autorización previa de Gerencia.
- **Sin comprobante no hay pago** — el pago a proveedor exige comprobante
  conforme entregado por Compras (RN-CMP-014); ni con proveedor de confianza
  se salta (coherente con RN-CMP-005/006).
- **Idempotencia en pagos** — un mismo comprobante no se paga dos veces; el
  ERP bloquea el doble pago (principio de idempotencia del proyecto).
- **Cadena de custodia intacta** — el efectivo pasa cajero → supervisor →
  Contabilidad (RN-MDP-002); cada relevo se autentica.
- **La caja chica se concilia antes de reponer** — sin rendición conciliada no
  hay reposición del fondo (RN-CMP-013).

## Principios de finanzas

- **El flujo de caja se proyecta, no se adivina** — la liquidez se anticipa
  con la proyección semanal; una alerta de liquidez sube a Gerencia.
- **El presupuesto lo aprueba Gerencia** — Finanzas prepara los insumos; la
  aprobación es de Gerencia (PROC-GER-001).
- **El margen mínimo se define con Comercial** — RN-CML-001; ningún precio se
  fija por debajo del margen objetivo sin aprobación.

## Cumplimiento tributario

- El registro para efectos tributarios sigue el
  [marco legal del área](marco-legal-contabilidad.md); el grupo trabaja con un
  **contador externo** para la declaración y presentación ante SUNAT
  (coherente con el modelo de RRHH, ver [área RRHH](../rrhh/README.md)).
- Los plazos SUNAT no se incumplen; una fecha límite próxima es una alerta,
  no una sorpresa.
