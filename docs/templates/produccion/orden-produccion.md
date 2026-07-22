<!-- Plantilla: Orden de producción | Módulo Producción | Ver README.md para convención de campos -->
<!-- Uso: SOP plan-produccion-cronograma. Costeo y desperdicio: autogenerados por el ERP, no se calculan a mano. -->

# ORDEN DE PRODUCCIÓN

**Subreceta/artículo:** [[ COMPLETAR ]] · **Cantidad:** [[ ]] ·
**Almacén:** [[ COMPLETAR: cocina de producción ]] · **Fecha:** {{ hoy }} ·
**Plan vinculado:** [[ COMPLETAR: plan de producción del turno, o "fuera de plan" ]]

## Insumos, desperdicio y costo (autogenerado)

| Insumo/subreceta | Cantidad consumida | Desperdicio esperado (receta) | Tipo de desperdicio | Peso desperdicio real | Costo unitario |
|---|---|---|---|---|---|
| [[ COMPLETAR ]] | {{ auto }} | {{ receta_item.merma_pct }} | [[ COMPLETAR: ej. cáscara ]] | {{ auto: balanza }} | {{ auto }} |
| [[ COMPLETAR ]] | {{ auto }} | {{ receta_item.merma_pct }} | [[ COMPLETAR: ej. semilla ]] | {{ auto: balanza }} | {{ auto }} |

> Una fila por insumo y tipo de desperdicio (ej. tomate → una fila
> "cáscara", otra "semilla"). Peso real se pesa en balanza y se registra
> directo en el ERP — no se transcribe a mano en este documento.

## Producción

**Lotes producidos:** {{ auto: código(s) de lote }} ·
**Merma no aprovechable (fuera de lo esperado en receta):**
[[ COMPLETAR, opcional ]] — motivo: [[ COMPLETAR ]]

## Costeo de la orden (calculado por el ERP, RN-PRD-018)

**Horas-hombre registradas:** [[ COMPLETAR ]] ·
**Costo de insumos (Σ consumido × costo unitario):** {{ auto }} ·
**Costo de mano de obra (horas-hombre × tarifa):** {{ auto }} ·
**Costo real unitario del producto aprovechable:** {{ auto }}

## Control de calidad

☐ Conforme — habilitado para despacho ·
☐ No conforme, reprocesado ·
☐ No conforme, desechado — ver [ficha-no-conformidad.md](ficha-no-conformidad.md)

---

<sub>Toda orden pasa control de calidad antes de habilitarse para
despacho al almacén central (RN-PRD-013). No conforme siempre genera
ficha de no conformidad, sin excepción. El costeo lo calcula el ERP, el
jefe de cocina solo registra horas-hombre y verifica el resultado.</sub>
