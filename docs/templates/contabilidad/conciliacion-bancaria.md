<!-- Plantilla: Conciliación bancaria | Área Contabilidad | Ver README.md para convención de campos -->
<!-- Uso: SOP conciliacion-bancaria (PROC-CTB-004). Obligatoria antes del cierre de periodo. -->

# CONCILIACIÓN BANCARIA

**Empresa:** [[ COMPLETAR: RUC/razón social ]] · **Cuenta:** [[ COMPLETAR: banco / N.° ]]
**Periodo:** [[ COMPLETAR ]] al [[ COMPLETAR ]] · **Concilia:** {{ usuario }} · **Fecha:** {{ hoy }}

## Saldos

| Concepto | Monto |
|---|---|
| Saldo según ERP | S/ [[ COMPLETAR ]] |
| Saldo según extracto bancario | S/ [[ COMPLETAR ]] |
| **Diferencia** | **S/ [[ COMPLETAR ]]** |

## Partidas conciliatorias

| Tipo | Descripción | Monto | Acción |
|---|---|---|---|
| En banco, no en ERP | [[ ej. comisión ]] | S/ [[ ]] | ☐ Registrado en ERP |
| En ERP, no en banco | [[ ej. cheque no cobrado ]] | S/ [[ ]] | ☐ En tránsito ☐ Corregido |
| [[ ]] | [[ ]] | S/ [[ ]] | [[ ]] |

**Tras conciliar:** ☐ Saldo ERP = saldo banco ☐ Solo partidas en tránsito
identificadas — detalle: [[ COMPLETAR ]]

## Visto de Gerencia

☐ Revisado y visado — {{ usuario_gerencia }} · fecha: [[ COMPLETAR ]]

---

<sub>Toda diferencia se explica y documenta; los duplicados se reversan con
asiento inverso, no se borran (RN-CTB-002). Sin conciliación visada no cierra
el periodo (RN-CTB-006).</sub>
