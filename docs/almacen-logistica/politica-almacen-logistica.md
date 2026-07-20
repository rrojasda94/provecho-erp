# Política de Almacén y Logística — Grupo Majambo

Referencia operativa del área. No reemplaza el criterio de Contabilidad
(costeo) ni de Producción (recetas) — donde el número no está definido, se
marca `[[ COMPLETAR ]]`.

## 1. FEFO/FIFO (RN-ALM-007)

Todo movimiento de salida de almacén sigue **FEFO** (first expired, first
out) para artículos con vencimiento, y **FIFO** (first in, first out) para
los que no lo tienen pero sí rotación (ej. empaques). Nunca se acomoda el
almacén "por conveniencia de acceso" si eso rompe el orden de salida.

## 2. Conteo y ajuste

- La periodicidad de conteo de Almacén Central es configurable en el ERP
  (RN-INV-007); mínimo un conteo cíclico [[ COMPLETAR: definir frecuencia,
  sugerido semanal por categoría rotativa ]] además de un conteo general
  [[ COMPLETAR: sugerido mensual o trimestral ]].
- Un conteo es de rutina (programado) o parte de un proceso de
  ajuste/auditoría puntual (RN-INV-014).
- Un ajuste es válido sin generar alarma solo dentro del margen de error
  definido entre Almacén y Contabilidad (RN-INV-015); fuera de margen
  dispara auditoría. Margen vigente: [[ COMPLETAR: definir con
  Contabilidad ]].
- Un ajuste se origina por sobrante, faltante, merma/daño o error de
  registro (RN-INV-016) — el motivo siempre se declara, nunca "ajuste
  genérico".
- Solicitar un ajuste y autorizarlo son permisos distintos (RN-INV-006); el
  encargado de almacén solicita, [[ COMPLETAR: definir quién autoriza —
  administrador o supervisor de logística ]] autoriza.

## 3. Punto de reorden — quién hace qué

El punto de reorden = (demanda diaria × tiempo de entrega) + stock de
seguridad (RN-INV-013). **Quién define** el stock mínimo/máximo de cada
artículo: Producción, Contabilidad y Logística en conjunto (RN-INV-008) —
Almacén aporta el dato real de consumo y rotación. **Quién actúa** cuando se
alcanza el punto de reorden: Compras ejecuta la compra (ver
[perfil de encargado de compras](../compras/perfiles/encargado-compras.md)).
Almacén no compra; reporta y alimenta el cálculo.

## 4. Vencimiento y merma

- Fecha de vencimiento: la declara el proveedor (compra) o se calcula desde
  la apertura en sucursal según la regla del artículo (RN-VNC-001/002/003).
- Producto próximo a vencer se prioriza en FEFO y se reporta antes de
  llegar al vencimiento real — no se espera a que venza para actuar.
- Toda merma se reporta en el módulo de inventario o producción, se
  estudia y rinde cuentas ante Almacén y Contabilidad (RN-INV-017).
- Todo desperdicio se reporta en producción; puede asociarse a una receta
  como producto derivado (RN-INV-018) — Almacén reporta el que detecta en
  su propio manejo (ej. rotura de empaque), Producción el que se genera en
  cocina.
- El stock de merma/dañado es subtipo de stock reservado: no apto para
  actividad económica, pendiente de auditoría y desecho (RN-INV-012).

## 5. Devoluciones

- Toda devolución retorna el producto a su almacén de origen por razón
  justificada (vencido, dañado, incumplimiento de plazo, ya no requerido,
  error al solicitar, duplicidad) y se dirige a desecho, auditoría o
  reintegro a stock disponible (RN-INV-019).
- Devolución a **proveedor** (compra externa): genera reporte al área de
  almacén, coordinado con Compras para el reclamo/nota de crédito
  (RN-INV-020).
- Devolución **sucursal → central**: ya cubierta en
  [recepcion-requerimiento-devoluciones](../diagrams/Procesos/Logistica-Almacen/Abastecimiento-Locales/recepcion-requerimiento-devoluciones.md).

## 6. Transferencias laterales entre sucursales

Excepción al flujo normal (sucursal↔central): una sucursal presta insumo a
otra directamente, sin pasar por Almacén Central.

- Solo ante necesidad real (quiebre de stock que no espera al ciclo normal
  de requerimiento) — no reemplaza la planificación normal.
- Requiere guía igual que cualquier salida de almacén (RN-ALM-001) y
  aprobación del encargado de almacén o supervisor, aunque no sea Almacén
  Central quien despacha.
- Se registra como transferencia en el ERP: descuenta origen al salir, suma
  destino al recibir (RN-INV-003), igual que cualquier transferencia.

## 7. Transporte (flota propia)

- Vehículo(s) propio(s) del grupo para reparto central↔sucursales y
  transferencias laterales.
- Cada vehículo se asigna a un responsable (chofer/repartidor o encargado
  de almacén) que rinde cuentas de su uso y de posibles daños/pérdidas
  (RN-VEH-002).
- Registro de kilometraje obligatorio en cada ruta — da fe del buen uso y
  cumplimiento de rutas (RN-VEH-004).
- Adquisición de vehículo nuevo la ve Compras, evaluando junto a Almacén el
  tipo de vehículo necesario (RN-VEH-001) — sigue el SOP de
  [búsqueda y negociación de activos](../diagrams/Procesos/Compras/Activos-Equipamiento/busqueda-negociacion-activos.md).
- Mantenimiento del vehículo sigue RN-MNT-001 a 004 (frecuencia
  recomendada, coordinación con proveedor de servicio vía Compras, reporte
  ante desperfecto).

## Referencias

- Reglas de negocio: RN-ALM-*, RN-INV-*, RN-VNC-*, RN-VEH-*, RN-MNT-* en [business-rules.md](../domain/business-rules.md)
- Glosario: Almacén Central, Stock, Movimiento, Transferencia, Merma, Desperdicio, Conteo, Ajuste, Devolución, Vehículo en [glossary.md](../foundation/glossary.md)
- SOPs del área: [docs/diagrams/Procesos/Logistica-Almacen/](../diagrams/Procesos/Logistica-Almacen/)
- Spec técnica del módulo: [src/modules/inventory/README.md](../../src/modules/inventory/README.md)
