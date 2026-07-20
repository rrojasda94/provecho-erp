<!-- Plantilla: Contrato de trabajo a tiempo parcial | Módulo RRHH | Ver README.md para convención de campos -->
<!-- Base legal: art. 4, D.S. 003-97-TR; arts. 11-13, D.S. 001-96-TR; régimen microempresa D.S. 013-2013-PRODUCE. -->
<!-- Solo si la jornada promedio es MENOR a 4 h/día (jornada semanal ÷ días laborables < 4). -->
<!-- OBLIGATORIO: por escrito y COMUNICAR AL MTPE dentro de 15 días naturales de suscrito (gestiona el contador). -->

# CONTRATO DE TRABAJO A TIEMPO PARCIAL

Conste por el presente documento el contrato de trabajo a tiempo parcial que
celebran, de una parte, **{{ empresa.razon_social }}**, con RUC N.°
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
[[ COMPLETAR: número/fecha ]]. La relación se rige por el régimen laboral
especial de la microempresa y por las normas del contrato a tiempo parcial.

## SEGUNDA — Puesto y funciones

EL TRABAJADOR ocupará el puesto de **{{ trabajador.cargo }}** en la sucursal
{{ sucursal.nombre }} ({{ sucursal.direccion }}), con las funciones del
perfil del puesto que declara conocer.

## TERCERA — Jornada a tiempo parcial

La jornada es de **[[ COMPLETAR: N.° horas semanales ]] horas semanales**,
distribuidas en [[ COMPLETAR: días y franjas horarias — ej. "viernes, sábado
y domingo de 18:00 a 22:00" ]], con un promedio **inferior a cuatro (4)
horas diarias** computado entre los días laborables de la semana. EL
TRABAJADOR registra su asistencia en el sistema de EL EMPLEADOR.

<!-- Si los turnos reales superan el promedio de 4 h/día, este contrato pierde su naturaleza parcial. No usar horas extra de forma habitual en este contrato. -->

## CUARTA — Plazo

[[ COMPLETAR: elegir — "El contrato es de duración indeterminada e inicia el
{{ contrato_laboral.fecha_inicio }}." / "El contrato rige del
{{ contrato_laboral.fecha_inicio }} al {{ contrato_laboral.fecha_fin }},
bajo la modalidad de [modalidad] justificada en la siguiente causa objetiva:
[causa concreta]." ]]

## QUINTA — Remuneración

EL TRABAJADOR percibirá una remuneración de
**S/ {{ contrato_laboral.remuneracion }}
([[ COMPLETAR: monto en letras ]] y 00/100 soles)**
[[ COMPLETAR: mensual / por periodo ]], proporcional a la jornada pactada y
no inferior al mínimo legal proporcional, pagadera mediante
[[ COMPLETAR: medio de pago ]], con los descuentos de ley.

## SEXTA — Beneficios

EL TRABAJADOR goza de los derechos que la normativa reconoce al trabajador a
tiempo parcial dentro del régimen de microempresa: descanso semanal,
feriados, cobertura de salud [[ COMPLETAR: SIS / ESSALUD ]] y régimen
pensionario conforme a su ficha. Se deja constancia de que, por la
naturaleza parcial de la jornada, no corresponden los beneficios que la ley
condiciona a una jornada mínima de 4 horas diarias
[[ COMPLETAR: alcance del descanso vacacional en jornada parcial — definir
redacción final con el abogado ]].

## SÉPTIMA — Obligaciones de EL TRABAJADOR

Cumplir los SOP, políticas internas y protocolos de higiene e inocuidad;
mantener vigente el carné de sanidad cuando el puesto lo exija; usar y
devolver el uniforme conforme al acta; guardar reserva de información
interna del negocio.

## OCTAVA — Comunicación al MTPE

El presente contrato se comunica al Ministerio de Trabajo y Promoción del
Empleo dentro de los quince (15) días naturales de su suscripción, conforme
a ley.

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
RN-RRHH-007). Verificar con el contador la comunicación al MTPE (15 días) y
que los turnos programados en el ERP nunca superen el promedio de 4 h/día —
un "parcial" con jornada real mayor es contingencia directa en
inspección.</sub>
