# Política de Marketing — Grupo Majambo

Referencia operativa del área. No reemplaza el criterio de Comercial
(precio/margen/oportunidad de venta) ni de Manejo de marca (identidad).
Donde una cifra no está definida, se marca `[[ COMPLETAR ]]`.

## 1. Gestión de marca y naming

- Marketing es el **dueño operativo de las marcas** (RN-MKT-001): su buen
  uso, consistencia, contenido y naming, aplicando los lineamientos de
  identidad (RN-MAR-003) sin capas de aprobación extra para el trabajo
  cotidiano — no se complica la burocracia.
- Solo lo **reservado a la sociedad** excede a Marketing: modificación
  estructural de la identidad de una marca o cesión/venta de PI
  (RN-MAR-004, RN-GRP-006) — eso lo deciden socios/holding.
- El **naming** de un producto o campaña lo define/valida Marketing,
  asegurando disponibilidad, coherencia con la marca y ausencia de
  conflicto (verificación de registro/legal si aplica, RN-MKT-007).
- Ante duda entre "se ve bien" y "es fiel a la marca", gana la marca.

## 2. Contenido: pertinencia sobre viralidad

- Todo contenido publicado responde a la marca y su público objetivo, no
  solo al alcance (RN-MKT-002). Contenido que gana viralidad a costa de la
  coherencia de marca **no se publica**.
- El contenido se planifica en un calendario, no se improvisa reacción por
  reacción — ver
  [plan-contenido-redes](../diagrams/Procesos/Marketing/Marca-Contenido/plan-contenido-redes.md).

## 3. Campañas: brief y objetivo medible

- Toda campaña tiene un **brief aprobado** antes de salir a canal:
  objetivo, público, canal, mensaje, presupuesto y KPI (RN-MKT-003).
- Campaña de impulso de venta define el objetivo comercial **con
  Comercial** (extiende
  [coordinacion-marketing-leads](../diagrams/Procesos/Comercial/Metas-Desempeno/coordinacion-marketing-leads.md)):
  Marketing atrae el lead, Comercial cierra la venta e investiga la
  oportunidad. La conversión se mide contra la venta real en el ERP.
- Campaña de marca/grupo (no de un producto) se declara así desde el
  inicio y se mide por alcance/reconocimiento, no por venta directa.
- El gasto de campaña sale del **presupuesto anual** de Marketing
  aprobado con Gerencia (RN-GER-007): dentro del presupuesto y bajo el
  límite, Marketing ejecuta autónomo; sobre el límite o fuera de lo
  presupuestado, aprueba Gerencia (matriz de aprobaciones, RN-GER-003).
  Límite `[[ COMPLETAR: definir en la reunión anual de presupuesto ]]`.

## 4. Material promocional y sucursales

- El material promocional se **especifica y valida** por Marketing, pero
  su compra pasa por el flujo de **Compras** (OC con proveedor, o caja
  chica según monto — RN-CMP-*); Marketing no compra por fuera
  (RN-MKT-004).
- Toda sucursal debe quedar **correctamente implementada** con el material
  vigente, tanto de producto **nuevo** como **clásico**; Marketing
  **verifica la implementación** en sucursal, no basta con enviar el
  material (RN-MKT-005) — ver
  [material-promocional-sucursales](../diagrams/Procesos/Marketing/Proveedores-Agencias/material-promocional-sucursales.md).

## 5. Agencias vs. propuesta interna

- La evaluación de una propuesta de agencia externa (o de la alternativa
  interna) la hace **Marketing**, por su mejor conocimiento del servicio,
  contra el objetivo y el presupuesto (RN-MKT-006). **Gerencia valida** la
  decisión — no la evalúa Compras.
- La agencia es un **servicio**: se formaliza por contrato (visado,
  RN-CTR-002/003) y el pago lo ejecuta Contabilidad (RN-CPP-006). No pasa
  por el flujo de compra de material (eso es solo para bienes, RN-MKT-004).
- Criterio de decisión agencia vs. interno: alcance requerido,
  especialización, costo y plazo — documentado en la
  [ficha de evaluación de propuesta](../templates/marketing/ficha-evaluacion-propuesta-agencia.md).

## 6. Coordinación con otras áreas

- **Comercial**: objetivo comercial, promociones vigentes a comunicar,
  consistencia con el guion de atención, atribución lead→venta.
- **Producción/I+D+i**: fecha real de disponibilidad de un producto nuevo
  antes de anunciar su lanzamiento (no se promociona algo sin stock/
  capacidad, RN-CML-005).
- **Compras**: adquisición del **material** promocional (bien). La
  **agencia** (servicio) no pasa por Compras — la evalúa Marketing, la
  valida Gerencia, se paga por Contabilidad.
- **Gerencia**: aprobación de presupuesto y campañas sobre umbral.
- **Socios / holding**: solo la modificación **estructural** de la
  identidad de una marca o la venta de PI (fuera del alcance de Marketing,
  RN-MAR-004). El resto de la gestión de marca es de Marketing.

## Referencias

- Reglas de negocio: RN-MKT-*, RN-MAR-003/004, RN-CML-002/003/005, RN-CMP-*, RN-CTR-002/003, RN-GER-003 en [business-rules.md](../domain/business-rules.md)
- Glosario: Marketing, Lead, Campaña, Naming, Marca en [glossary.md](../foundation/glossary.md)
- SOPs del área: [docs/diagrams/Procesos/Marketing/](../diagrams/Procesos/Marketing/)
- Módulo backend (slice core desde 2026-08-01): [src/modules/marketing/README.md](../../src/modules/marketing/README.md)
