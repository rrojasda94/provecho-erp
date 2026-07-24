# SOP — Pago a proveedor

**Área:** Contabilidad · **Grupo:** Tesorería
**Basado en:** PROC-CTB-003 · **Relacionado:** PROC-CMP-001 (Compras), RN-CMP-014, RN-CTB-005

## Objetivo
Ejecutar el pago al proveedor de forma trazable, solo con comprobante conforme
y con la aprobación que corresponda, aplicando detracción cuando el ítem esté
afecto — sin doble pago ni pagos sin sustento.

## Frecuencia
Según el plazo de pago pactado con cada proveedor (contado, crédito 7/15/30
días). Se revisa la cola de pagos por vencer al menos una vez por semana.

## Responsable
Contador/tesorero (ejecuta). Gerencia aprueba los pagos sobre el umbral antes
de ejecutarse.

## Materiales y equipo
- ERP con módulo de contabilidad/tesorería (cola de comprobantes por pagar)
- Acceso a banca electrónica de la empresa
- Ficha del proveedor (condición y plazo de pago, cuenta bancaria, cuenta de
  detracciones)

## Pasos — Contador/tesorero
1. Tomar de la cola los comprobantes **conformes** entregados por Compras
   (recepción validada y comprobante registrado, RN-CMP-014). Si no está
   conforme, no se paga — devolver a Compras.
2. Verificar que el comprobante no esté ya pagado; el ERP bloquea el doble pago
   (idempotencia). Si aparece pagado, detener y revisar.
3. Confirmar plazo y fecha de vencimiento del pago según la ficha del
   proveedor; priorizar por vencimiento.
4. Determinar si la operación está afecta a **detracción (SPOT)**. Si lo está,
   calcular el monto a detraer y separar el depósito a la cuenta de
   detracciones del proveedor.
5. Si el monto supera el **umbral** configurado, solicitar aprobación de
   Gerencia y esperar la autorización antes de continuar (RN-CTB-005).
6. Ejecutar el pago por el medio pactado (transferencia, cheque, efectivo de
   caja si aplica); de haber detracción, depositarla primero o en simultáneo.
7. Registrar el pago en el ERP, adjuntando la constancia (voucher/transferencia
   y, si aplica, constancia de detracción). El ERP asienta el egreso.
8. Marcar el comprobante como pagado; la cola se actualiza.

## Pasos — Gerencia (solo pagos sobre umbral)
9. Revisar el comprobante, el monto y el sustento; aprobar o rechazar en el
   ERP con usuario + PIN. Sin aprobación, el pago no se ejecuta.

## Excepciones
- Comprobante no conforme o sin recepción validada → no se paga; se devuelve a
  Compras para regularizar.
- Proveedor sin cuenta bancaria registrada o datos incompletos → completar la
  ficha del proveedor antes de pagar.
- Operación afecta a detracción y no se deposita el SPOT → se pierde el crédito
  fiscal y hay multa; no ejecutar el pago sin resolver la detracción.
- Falta de liquidez para pagar en fecha → escalar a Gerencia con la proyección
  de flujo de caja; renegociar plazo con el proveedor si corresponde.
- Pago urgente fuera de la cola → requiere aprobación explícita de Gerencia,
  cualquiera sea el monto.

## Problemas frecuentes
Sin incidentes reportados aún — completar cuando el equipo identifique errores
recurrentes (p. ej. comprobantes que llegan sin conformidad, detracciones mal
calculadas).

## Checklist de verificación
- [ ] Comprobante conforme entregado por Compras (RN-CMP-014)
- [ ] No estaba pagado (sin doble pago)
- [ ] Plazo/vencimiento confirmado contra la ficha del proveedor
- [ ] Detracción evaluada y depositada si aplica
- [ ] Aprobación de Gerencia si supera el umbral (RN-CTB-005)
- [ ] Pago registrado con constancia adjunta; comprobante marcado como pagado

## Evidencia y supervisión
Cada pago queda en el ERP con usuario + PIN, monto, medio, constancia y —si
aplica— la aprobación de Gerencia y la constancia de detracción, con valor
anterior/nuevo. Los pagos sobre umbral sin aprobación no pueden ejecutarse; el
intento queda registrado.
