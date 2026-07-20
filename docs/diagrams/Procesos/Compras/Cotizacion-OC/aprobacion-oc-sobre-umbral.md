# SOP — Aprobación de OC sobre el umbral

**Área:** Compras · **Grupo:** Cotización y OC

## Objetivo
Que ninguna compra grande se comprometa sin el visto bueno de quien
responde por el presupuesto — el umbral existe para que el encargado de
compras opere ágil en lo chico y consulte en lo que sí duele si sale mal.

## Frecuencia
Cada OC cuyo monto total supera el umbral configurado.

## Responsable
Administrador/gerente aprueba; encargado de compras solicita.

## Materiales y equipo
- Borrador de OC con monto calculado
- Umbral vigente: [[ COMPLETAR: definir monto en soles — permiso
  `purchases.aprobar` en el ERP ]]
- Cotizaciones comparadas que sustentan la elección del proveedor

## Pasos
1. El ERP marca automáticamente la OC como "pendiente de aprobación" si el
   monto supera el umbral — no se emite hasta resolver esto.
2. Encargado de compras presenta al administrador: proveedor elegido,
   monto, comparativo de cotizaciones, motivo de la compra (reposición
   normal, insumo nuevo, urgencia).
3. Administrador revisa contra presupuesto/caja disponible y aprueba o
   rechaza, con comentario si rechaza.
4. Si aprueba → la OC se libera para emisión (SOP emisión de OC continúa).
5. Si rechaza → encargado de compras ajusta (menor cantidad, otro proveedor,
   fraccionar la compra) o escala si la compra es indispensable pese al
   costo.
6. Registrar la decisión (aprobada/rechazada, quién, cuándo) en el ERP —
   queda ligada a la OC para auditoría.

## Excepciones
- Emergencia operativa real (insumo crítico agotado, riesgo de parar
  producción) → el administrador puede aprobar verbal/por mensaje de forma
  inmediata, pero se registra en el ERP dentro de las siguientes 24 horas —
  no queda sin registro.
- Si el administrador no está disponible → definir suplente de aprobación
  [[ COMPLETAR: quién aprueba en su ausencia ]]; nunca se fracciona la
  compra en varias OC menores al umbral para evitar la aprobación (eso es
  la señal de alerta más común de mal uso del control).

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Compras grandes "se enteran después" | Sin bloqueo real en el ERP | Paso 1: bloqueo automático por umbral, no depende de que alguien avise |
| OC fraccionadas justo debajo del umbral | Se evita la aprobación a propósito | Auditar patrones de OC seguidas al mismo proveedor por montos similares |
| Aprobación sin criterio, solo "ya, dale" | Sin comparativo presentado | Paso 2: comparativo de cotizaciones siempre en la solicitud |

## Checklist de verificación
- [ ] OC bloqueada automáticamente al superar el umbral
- [ ] Comparativo de cotizaciones presentado
- [ ] Decisión tomada con motivo registrado
- [ ] Si emergencia: registrada en ERP dentro de 24 h
- [ ] Sin fraccionamiento de compras para evitar el umbral

## Evidencia y supervisión
Historial de aprobaciones/rechazos en el ERP, ligado a cada OC. Auditoría
trimestral de OCs cercanas al umbral (posible fraccionamiento).
