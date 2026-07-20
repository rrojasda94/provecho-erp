# SOP — Cobro y emisión de comprobante de pago

**Área:** Comercial · **Grupo:** Cobros
**Basado en:** PROC-COM-002

## Objetivo
Cobrar el monto correcto por el medio de pago elegido y emitir el comprobante
que corresponde, sin diferencias de caja ni comprobantes mal emitidos.

## Frecuencia
Cada cobro, ya sea inmediato (en sucursal) o post-entrega (delivery).

## Responsable
Cajero (atención al cliente) / Repartidor-Deliverista (cobro en la puerta del
cliente, cuando aplica).

## Materiales y equipo
- Datáfono / POS de pago con tarjeta
- Lámpara UV o marcador de billetes falsos
- ERP con módulo de cobro y emisión de comprobantes

## Pasos — Cobro (inmediato o post-entrega)
1. El cliente elige el medio de pago: billetera digital, link de pago,
   transferencia, tarjeta o efectivo (efectivo/POS solo disponible en
   sucursal).
2. Billetera digital, link de pago o transferencia → cobrar por ese canal.
3. Efectivo → verificar los billetes con luz UV, marcador o contraluz antes de
   aceptarlos. Si el monto no es exacto, calcular el vuelto óptimo (mínimo de
   billetes/monedas) y entregarlo verificando que sea exacto.
4. Tarjeta/POS → verificar el monto ingresado en el dispositivo antes de
   confirmar, y registrar el pago en el POS (voucher).
5. Confirmar que la transacción fue exitosa.
6. Preguntar si desea boleta (con o sin DNI) o factura (con RUC).
7. Verificar que el método de pago que se va a registrar coincida exactamente
   con el que usó el cliente, antes de emitir — nunca emitir el comprobante
   antes de confirmar el pago.
8. Emitir el comprobante correspondiente.
9. Preguntar el medio de entrega del comprobante (físico o digital) y
   entregarlo.

## Pasos — Reconciliación de cobro post-entrega (Repartidor → Cajero)
9. El repartidor entrega al cajero el dinero o voucher cobrado en la puerta
   del cliente.
10. El cajero verifica que el monto entregado esté completo.
11. Si el pago fue con tarjeta o billetera digital: ingresar el lote y la
    referencia del voucher a la pasarela de pago.

## Excepciones
- Transacción no efectuada → generar el reporte detallado y mostrarlo al
  cliente. Si el cliente se opone, insistir explicando la garantía (reclamo
  bancario en 48h, o devolución si la empresa detecta doble cobro); si acepta,
  reintentar el medio de pago.
- Repartidor entrega monto incompleto → exigir el monto completo de inmediato;
  si no se resuelve en el momento, reportar la falla del trabajador sin
  demora.
- Cliente se niega a dar DNI para la boleta → emitir boleta simple, sin DNI.
- Comprobante ya emitido con el método de pago incorrecto → corregir el
  método de pago en el ERP antes del cierre de caja, no dejarlo para después.

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Descuadre de caja, trabajo extra para contabilidad | El cajero digita mal el método de pago al emitir el comprobante | Verificar el método de pago antes de emitir; nunca emitir el comprobante antes de confirmar el pago; si ya ocurrió el error, corregirlo en el ERP antes del cierre de caja |

## Checklist de verificación
- [ ] Billetes verificados antes de aceptar efectivo
- [ ] Vuelto entregado exacto
- [ ] Transacción confirmada como exitosa antes de cerrar la venta
- [ ] Comprobante correcto emitido (boleta/factura) según lo pedido por el
      cliente
- [ ] Pago registrado con el o los medios de pago efectuados.
- [ ] Monto de cobro post-entrega verificado completo al recibirlo del
      repartidor

## Evidencia y supervisión
Encargado de tienda/supervisor revisa reportes de transacciones no efectuadas
y descuadres de repartidores al cierre de cada turno. Ver también
[Apertura de caja](../../Contabilidad/Caja/apertura-caja-pos.md) y
[Cierre de caja](../../Contabilidad/Caja/cierre-caja-pos.md) para el cuadre
general de caja.
