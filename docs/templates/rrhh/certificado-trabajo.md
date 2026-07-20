<!-- Plantilla: Certificado de trabajo | Módulo RRHH | Ver README.md para convención de campos -->
<!-- Base legal: art. 45, D.S. 001-96-TR. Emitir dentro de 48 h del cese (RN-RRHH-002). -->

# CERTIFICADO DE TRABAJO

{{ empresa.razon_social }}, con RUC N.° {{ empresa.ruc }} y domicilio fiscal
en {{ empresa.domicilio_fiscal }}, deja constancia de que:

Don(ña) **{{ trabajador.nombres }} {{ trabajador.apellidos }}**,
identificado(a) con {{ trabajador.tipo_documento }} N.°
{{ trabajador.numero_documento }}, prestó servicios para nuestra empresa
durante el periodo comprendido entre el **{{ trabajador.fecha_ingreso }}** y
el **{{ trabajador.fecha_cese }}**, acumulando un tiempo de servicios de
**{{ certificado_trabajo.tiempo_servicios }}**.

Durante dicho periodo se desempeñó en el(los) cargo(s) de:

- {{ certificado_trabajo.cargos }}

<!-- Bloque opcional: solo se incluye si el trabajador lo solicita (art. 45 D.S. 001-96-TR) -->
[[ OPCIONAL — solo a solicitud del trabajador:
Asimismo, se deja constancia de que durante su permanencia demostró
{{ certificado_trabajo.conducta_desempeno }}. ]]

Se expide el presente certificado a solicitud del(la) interesado(a), para
los fines que estime conveniente.

{{ empresa.ciudad }}, {{ hoy }}.

<br>

_______________________________
{{ representante.nombres }} {{ representante.apellidos }}
{{ representante.cargo }}
{{ empresa.razon_social }}

---

<sub>⚠ Visado legal requerido antes de uso (RN-RRHH-007). El certificado no
puede contener información que perjudique al trabajador sin su
consentimiento.</sub>
