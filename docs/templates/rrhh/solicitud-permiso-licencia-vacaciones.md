<!-- Plantilla: Solicitud de permiso / licencia / vacaciones | Módulo RRHH -->
<!-- Base legal vacaciones: D.Leg. 713. Sujeta a aprobación (RN-RRHH-005). -->

# SOLICITUD DE {{ solicitud_permiso.tipo }} N.° {{ solicitud_permiso.correlativo }}

**Fecha de solicitud:** {{ hoy }}

**Datos del trabajador**
- Nombres y apellidos: {{ trabajador.nombres }} {{ trabajador.apellidos }}
- Documento: {{ trabajador.tipo_documento }} {{ trabajador.numero_documento }}
- Cargo / área: {{ trabajador.cargo }} — {{ trabajador.area }}
- Sede: {{ sucursal.nombre }}

**Tipo de ausencia solicitada** (marcar uno):

- [ ] Vacaciones (D.Leg. 713 — 30 días/año)
- [ ] Licencia **con** goce de haber
- [ ] Licencia **sin** goce de haber
- [ ] Permiso por horas

**Periodo solicitado**
- Desde: {{ solicitud_permiso.fecha_desde }}
- Hasta: {{ solicitud_permiso.fecha_hasta }}
- Total: [[ COMPLETAR: N.° de días u horas ]]

**Motivo:** [[ COMPLETAR: motivo de la solicitud ]]

<br>

_______________________________
Firma del trabajador
{{ trabajador.nombres }} {{ trabajador.apellidos }}

---

## Resolución (uso del área responsable)

- [ ] **Aprobada**  [ ] **Rechazada**
- Motivo (si se rechaza): [[ COMPLETAR ]]
- Saldo de vacaciones (si aplica): {{ trabajador.saldo_vacaciones }} días

<br>

_______________________________
{{ aprobador.nombres }} {{ aprobador.apellidos }}
{{ aprobador.cargo }} — Fecha: {{ solicitud_permiso.fecha_resolucion }}

<sub>El goce de vacaciones debe coordinarse entre trabajador y empleador;
a falta de acuerdo, lo fija el empleador (D.Leg. 713).</sub>
