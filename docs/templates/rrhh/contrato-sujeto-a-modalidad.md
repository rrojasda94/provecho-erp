<!-- Plantilla: Contrato de trabajo sujeto a modalidad | Módulo RRHH | Ver README.md para convención de campos -->
<!-- Base legal: arts. 53-83, D.S. 003-97-TR (LPCL); régimen microempresa D.S. 013-2013-PRODUCE. -->
<!-- OBLIGATORIO: por escrito, con causa objetiva CONCRETA (cláusula tercera). Causa genérica o falsa = contrato indeterminado. -->
<!-- Ya no se registra ante MTPE (D.Leg. 1246). Entregar copia al trabajador dentro de 3 días hábiles. -->

# CONTRATO DE TRABAJO SUJETO A MODALIDAD

Conste por el presente documento el contrato de trabajo sujeto a modalidad
que celebran, de una parte, **{{ empresa.razon_social }}**, con RUC N.°
{{ empresa.ruc }}, domicilio fiscal en {{ empresa.domicilio_fiscal }},
representada por {{ representante.nombres }} {{ representante.apellidos }},
identificado(a) con {{ representante.tipo_documento }} N.°
{{ representante.numero_documento }}, en adelante **EL EMPLEADOR**; y, de la
otra parte, don(ña) **{{ trabajador.nombres }} {{ trabajador.apellidos }}**,
identificado(a) con {{ trabajador.tipo_documento }} N.°
{{ trabajador.numero_documento }}, con domicilio en
{{ trabajador.domicilio }}, en adelante **EL TRABAJADOR**:

## PRIMERA — Régimen laboral

EL EMPLEADOR es una **microempresa** acreditada en REMYPE con constancia
[[ COMPLETAR: número/fecha ]], por lo que la relación se rige por el régimen
laboral especial de la microempresa (D.S. 013-2013-PRODUCE) y,
supletoriamente, por el régimen común.

## SEGUNDA — Modalidad contractual

Las partes celebran un contrato bajo la modalidad de
**[[ COMPLETAR: elegir una — inicio o incremento de actividad (art. 57) /
necesidad de mercado (art. 58) / temporada (art. 67) / suplencia (art. 61) /
ocasional (art. 60) ]]**, conforme al D.S. 003-97-TR.

## TERCERA — Causa objetiva

<!-- La cláusula que sostiene todo el contrato. Hechos concretos, fechas, sucursal. -->
La contratación se justifica en la siguiente causa objetiva:
[[ COMPLETAR: descripción CONCRETA — ej. "la apertura de la sucursal X de la
marca Y, ubicada en Z, iniciada el DD/MM/AAAA, que constituye incremento de
actividad de EL EMPLEADOR y requiere personal para su puesta en marcha y
consolidación" / "el incremento coyuntural de la demanda por [hecho
verificable], que excede la capacidad del personal permanente" ]].

## CUARTA — Puesto y funciones

EL TRABAJADOR ocupará el puesto de **{{ trabajador.cargo }}** en la sucursal
{{ sucursal.nombre }} ({{ sucursal.direccion }}), con las funciones del
perfil del puesto que declara conocer, sin perjuicio de la asignación
razonable a otra sucursal o marca de EL EMPLEADOR.

## QUINTA — Plazo y periodo de prueba

El contrato rige del **{{ contrato_laboral.fecha_inicio }}** al
**{{ contrato_laboral.fecha_fin }}**
([[ COMPLETAR: duración en meses ]]), renovable por acuerdo escrito sin
exceder el plazo máximo legal de la modalidad
[[ COMPLETAR: 3 años en inicio/incremento de actividad; 5 años acumulando
modalidades (art. 74) ]]. Periodo de prueba:
[[ COMPLETAR: 3 meses — solo en el primer contrato; no se repite en
renovaciones del mismo puesto ]].

## SEXTA — Jornada y horario

Jornada de [[ COMPLETAR: N.° horas diarias/semanales ]] horas, en turnos
programados por EL EMPLEADOR, respetando los máximos legales, el descanso
semanal y el registro de asistencia en el sistema de EL EMPLEADOR.

## SÉPTIMA — Remuneración

Remuneración mensual de **S/ {{ contrato_laboral.remuneracion }}
([[ COMPLETAR: monto en letras ]] y 00/100 soles)**, pagadera
[[ COMPLETAR: forma y medio de pago ]], con los descuentos de ley.

## OCTAVA — Beneficios del régimen especial

Aplica la misma cláusula de beneficios del régimen microempresa que en el
contrato indeterminado: 15 días calendario de vacaciones por año, cobertura
de salud [[ COMPLETAR: SIS / ESSALUD ]], régimen pensionario según ficha, y
demás derechos del régimen especial mientras la acreditación REMYPE esté
vigente.

## NOVENA — Obligaciones de EL TRABAJADOR

Cumplir los SOP, políticas internas y protocolos de higiene e inocuidad;
mantener vigente el carné de sanidad cuando el puesto lo exija; usar y
devolver uniforme y equipos conforme al acta; guardar reserva de la
información interna del negocio.

## DÉCIMA — Extinción

El contrato termina al vencimiento del plazo sin necesidad de aviso, o por
las demás causas legales. La renovación es expresa y por escrito; de
continuar las labores después del vencimiento sin renovación, el contrato se
entiende de duración indeterminada (art. 77, D.S. 003-97-TR).

Firmado en dos ejemplares de igual tenor, en {{ empresa.ciudad }}, el
{{ hoy }}.

<br>

| EL EMPLEADOR | EL TRABAJADOR |
|---|---|
| _______________________________ | _______________________________ |
| {{ representante.nombres }} {{ representante.apellidos }} | {{ trabajador.nombres }} {{ trabajador.apellidos }} |
| {{ representante.cargo }} — {{ empresa.razon_social }} | {{ trabajador.tipo_documento }} N.° {{ trabajador.numero_documento }} |

---

<sub>⚠ Visado legal requerido antes del primer uso (RN-CTR-002 /
RN-RRHH-007). Antes de emitir: verificar plazos acumulados del trabajador en
el ERP (SOP elección de modalidad) y que la causa objetiva sea real y
verificable. Copia al trabajador en 3 días hábiles con cargo.</sub>
