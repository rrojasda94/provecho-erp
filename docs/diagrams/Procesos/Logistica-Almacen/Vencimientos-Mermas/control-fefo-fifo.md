# SOP — Control FEFO/FIFO en Almacén Central

**Área:** Almacén y Logística · **Grupo:** Vencimientos y Mermas

## Objetivo
Que siempre salga primero lo más próximo a vencer o lo más antiguo — el
motivo n.º 1 de merma evitable es despachar lo nuevo y dejar lo viejo atrás
del estante.

## Frecuencia
Continua — cada recepción y cada despacho.

## Responsable
Encargado de Almacén Central; todo el personal que despacha aplica la
regla.

## Materiales y equipo
- Etiquetado visible de fecha de vencimiento/ingreso por lote
- ERP: módulo de inventario con lote y fecha de vencimiento

## Pasos
1. Al recibir mercadería (compra o transferencia): registrar el lote con
   su fecha de vencimiento (o fecha de ingreso, si no tiene vencimiento) en
   el ERP.
2. Ubicar físicamente el producto de forma que lo más próximo a vencer/más
   antiguo quede accesible primero (adelante o arriba, según el layout del
   almacén) — nunca detrás de lo nuevo "porque hay más espacio ahí".
3. Al hacer picking para un despacho: el sistema sugiere el lote a tomar
   según FEFO/FIFO; tomar ese lote, no el más cómodo de alcanzar.
4. Si físicamente el lote sugerido no está donde debería (mal acomodado) →
   corregir el acomodo en el momento, no solo despachar el que sí se
   encuentra a mano.
5. Revisión visual periódica (parte de la ronda diaria del encargado):
   confirmar que el acomodo respeta FEFO/FIFO, no solo confiar en que el
   sistema lo sugiere bien si el acomodo físico está desordenado.

## Excepciones
- Producto que el cliente/receta exige de un lote específico (raro, pero
  posible por trazabilidad de un incidente) → se documenta la excepción y
  el motivo.
- Reacomodo grande de almacén (remodelación, cambio de layout) → puede
  romper el orden temporalmente; se prioriza restaurar FEFO/FIFO apenas
  termina el reacomodo, no se deja "para después".

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Se encuentra producto vencido al fondo del estante | Acomodo no respeta FEFO, lo nuevo tapa lo viejo | Paso 2: ubicar lo próximo a vencer siempre accesible primero |
| El sistema sugiere un lote pero no está donde debería | Acomodo físico desordenado | Paso 4: corregir en el momento, no despachar el que esté a mano |
| Merma alta pese a "tener FEFO" | Se sigue el sistema pero no se verifica el acomodo físico | Paso 5: revisión visual periódica, no solo confiar en el sistema |

## Checklist de verificación
- [ ] Lote y fecha registrados en cada recepción
- [ ] Acomodo físico respeta orden de salida
- [ ] Picking sigue el lote sugerido por el sistema
- [ ] Desajustes de acomodo corregidos en el momento
- [ ] Revisión visual periódica realizada

## Evidencia y supervisión
Se refleja en el indicador de merma por vencimiento del reporte mensual.
Administrador revisa tendencia de merma por esta causa específica.
