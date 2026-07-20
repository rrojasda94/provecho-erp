# SOP — Transferencia lateral entre sucursales

**Área:** Almacén y Logística · **Grupo:** Transporte y Transferencias

## Objetivo
Resolver un quiebre de stock urgente prestando entre sucursales, sin perder
trazabilidad ni saltarse el control de salida de almacén.

## Frecuencia
Excepcional — ante quiebre de stock que no puede esperar al ciclo normal de
requerimiento a Almacén Central.

## Responsable
Encargado de tienda de la sucursal que envía solicita/ejecuta; encargado de
Almacén Central o supervisor de logística aprueba.

## Materiales y equipo
- ERP: módulo de inventario (transferencia sucursal→sucursal)
- Plantilla: [guia-transferencia-lateral](../../../../templates/almacen-logistica/guia-transferencia-lateral.md)
- Vehículo disponible para el traslado (propio o coordinado con Almacén
  Central)

## Pasos
1. Sucursal con quiebre confirma que no puede esperar al ciclo normal de
   requerimiento (SOP conteo y requerimiento) — la transferencia lateral es
   excepción, no atajo de comodidad.
2. Identificar qué sucursal cercana tiene stock disponible del artículo
   (consulta en el ERP o coordinación directa entre encargados).
3. Solicitar aprobación al encargado de Almacén Central o supervisor de
   logística antes de mover el producto — no se transfiere sin
   autorización, aunque sea entre sucursales.
4. Con aprobación: generar la guía de transferencia en el ERP (obligatoria,
   RN-ALM-001 aplica también a movimientos entre sucursales).
5. Trasladar físicamente el producto (vehículo propio del grupo o el medio
   que corresponda), respetando cadena de frío si aplica.
6. Sucursal receptora confirma recepción en el ERP: cantidad y estado
   contra la guía — cualquier diferencia se registra (RN-INV-002).
7. La transferencia descuenta stock de la sucursal que envía y suma a la
   que recibe (RN-INV-003).

## Excepciones
- Emergencia que no admite esperar la aprobación previa (ej. cierre
  inminente de turno sin insumo crítico) → puede ejecutarse y registrarse
  la aprobación retroactiva el mismo día, documentando la urgencia — no se
  vuelve costumbre.
- Sin vehículo disponible en el momento → coordinar con Almacén Central si
  su vehículo puede desviarse en una ruta ya programada, antes de usar
  transporte no autorizado.

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Transferencias laterales se vuelven la forma normal de abastecerse | Sin control de cuándo es "excepción real" | Paso 1: confirmar que no puede esperar al ciclo normal, cada vez |
| Producto se mueve sin guía "porque es rápido y es entre locales" | Se asume que no aplica el control de salida | RN-ALM-001 aplica igual; paso 4 obligatorio |
| Nadie sabe qué sucursal tiene stock disponible | Sin consulta centralizada | Paso 2: consultar el ERP antes de llamar sucursal por sucursal |

## Checklist de verificación
- [ ] Confirmado que no puede esperar al ciclo normal
- [ ] Sucursal con stock disponible identificada
- [ ] Aprobación de Almacén Central/supervisor obtenida
- [ ] Guía de transferencia generada en el ERP
- [ ] Traslado respetando cadena de frío si aplica
- [ ] Recepción confirmada con diferencias registradas si las hay

## Evidencia y supervisión
Transferencias laterales quedan en el ERP con su aprobación. Administrador
revisa mensualmente la frecuencia por sucursal — frecuencia alta es señal
de mala planificación de requerimiento normal, no de sistema funcionando
bien.
