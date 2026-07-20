# SOP — Conteo de insumos de fin de jornada y envío de requerimiento

**Área:** Logística y Almacén · **Grupo:** Abastecimiento-Locales
**Basado en:** PROC-INV-001 (pasos 1-9)

## Objetivo
Declarar el stock real de fin de jornada con precisión y enviar a tiempo el
requerimiento correcto a Almacén Central, evitando quiebres de stock y
mermas por mal manejo.

## Frecuencia
Diaria, al cierre de cada jornada. Insumos sin descuento automático
(limpieza, menaje, servilletas, bolsas, etc.): según la periodicidad propia
de su lista de inventario.

## Responsable
Personal de cocina y Personal de atención al cliente (conteo) → Encargado
de tienda/Supervisor (validación y envío).

## Materiales y equipo
- Balanza
- Lector de código QR (si la sucursal lo tiene)
- ERP con módulo de inventario
- Guia de peso de envases

## Pasos — Personal de cocina / Personal de atención al cliente
1. Iniciar el conteo al menos 10 minutos antes del cierre de puertas, para
   dejar todo listo a tiempo.
2. Insumos refrigerados/congelados que ya están a medio usar: pesarlos en
   balanza, descontando el peso del envase.
3. Insumos que siguen sellados de Almacén Central: escanear el código QR, o
   sumar directamente el peso indicado al stock sin volver a pesarlos.
4. No dejar ningún insumo refrigerado/congelado más de 5 minutos fuera de
   refrigeración durante el conteo.
5. Contar aparte, según la periodicidad que le toque a su lista de
   inventario, los insumos que no se descuentan automáticamente del stock
   por venta (limpieza, menaje, servilletas, bolsas, etc.).
6. Ingresar el conteo al ERP — genera un borrador.

## Pasos — Encargado de tienda/Supervisor
7. Revisar la alerta del sistema, si aparece: se dispara cuando el stock
   declarado se desvía del margen de error configurado.
8. Validar el conteo verificando en persona los insumos principales o más
   costosos, para asegurarse de que corresponde con lo declarado por el
   personal.
9. Revisar el sugerido de requerimiento que calcula el ERP (según si hay
   stock suficiente o hace falta programar un envío).
10. Ajustar la cantidad sugerida a la baja si evalúa que no hace falta
    pedir tanto — el borrador es editable.
11. Aprobar y enviar el Requerimiento a Almacén Central vía ERP.

## Excepciones
- Alerta de desviación fuera del margen de error → no aprobar el conteo sin
  revisar la causa; puede disparar auditoría.
- Insumo refrigerado/congelado que superó los 5 minutos fuera de
  refrigeración durante el conteo → no reintegrarlo como si nada; evaluarlo
  como posible merma.
- Supervisor considera que no hace falta pedir tanto como sugiere el ERP →
  puede reducir la cantidad en el borrador antes de enviar; no puede pedir
  más de lo que el sistema calculó sin justificar (reserva grande, fiestas).
- Durante feriados, fiestas nacionales o locales, mantener el stock máximo
  de insumos principales.

## Problemas frecuentes
Sin incidentes reportados aún — completar esta tabla cuando el equipo
identifique errores recurrentes en el conteo.

## Checklist de verificación
- [ ] Conteo iniciado al menos 10 minutos antes del cierre
- [ ] Descontar el envase al pesar
- [ ] Insumos sellados escaneados o sumados por QR
- [ ] Insumos refrigerados/congelados expuestos por menos de 5 minutos
      fuera de refrigeración
- [ ] Insumos sin descuento automático contados según su periodicidad
- [ ] Insumos principales/más costosos verificados en persona por el
      Encargado/Supervisor
- [ ] Requerimiento aprobado y enviado a Almacén Central

## Evidencia y supervisión
El conteo, la validación del Encargado/Supervisor y el Requerimiento
enviado quedan registrados en el ERP. Ver también SOP de
[picking y despacho en almacén central](picking-despacho-almacen-central.md)
para el siguiente paso del proceso.
