<!-- Plantilla: Orden de pago | Área Contabilidad | Ver README.md para convención de campos -->
<!-- Uso: SOP pago-a-proveedor (PROC-CTB-003). Solo con comprobante conforme (RN-CMP-014). -->

# ORDEN DE PAGO

**N.°:** {{ correlativo }} · **Fecha:** {{ hoy }} · **Solicita:** {{ usuario }}

## Proveedor y comprobante

| Campo | Dato |
|---|---|
| Proveedor | [[ COMPLETAR: razón social / RUC ]] |
| Comprobante | [[ COMPLETAR: tipo, serie-número ]] |
| Conforme entregado por Compras | ☐ Sí (RN-CMP-014) |
| Fecha de vencimiento del pago | [[ COMPLETAR ]] |

## Importe

| Concepto | Monto |
|---|---|
| Importe del comprobante | S/ [[ COMPLETAR ]] |
| Detracción SPOT (si aplica) | S/ [[ COMPLETAR ]] |
| **Neto a transferir al proveedor** | **S/ [[ COMPLETAR ]]** |

**¿Afecto a detracción?** ☐ No ☐ Sí — % y cuenta: [[ COMPLETAR ]]
**Medio de pago:** ☐ Transferencia ☐ Cheque ☐ Efectivo — ref.: [[ COMPLETAR ]]

## Aprobación de Gerencia (si supera el umbral, RN-CTB-005)

☐ No requiere (bajo umbral) ☐ Aprobado — {{ usuario_gerencia }} · fecha: [[ COMPLETAR ]]
☐ Rechazado — motivo: [[ COMPLETAR ]]

## Ejecución

☐ Pagado — fecha: [[ COMPLETAR ]] · constancia adjunta: ☐ Sí
☐ Detracción depositada — constancia: ☐ Sí (si aplica)

---

<sub>Sin comprobante conforme no hay pago (RN-CMP-014). El ERP bloquea el doble
pago del mismo comprobante. Pago sobre umbral requiere aprobación previa de
Gerencia (RN-CTB-005).</sub>
