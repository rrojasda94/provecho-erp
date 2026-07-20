# Política comercial — Grupo Majambo

Referencia de precio, margen, ofertas/promociones y metas de venta. No
reemplaza el criterio de contabilidad ni de gerencia — donde el número no
está definido, se marca `[[ COMPLETAR ]]` en vez de inventarlo.

## 1. Precio y margen de contribución

**Margen de contribución** = precio de venta − costo variable (insumos +
empaque + comisión de medio de pago del canal). Es lo que cada venta aporta
para cubrir costos fijos y utilidad — no es lo mismo que "ganancia neta".

- Todo precio nuevo o revisado se calcula con margen de contribución
  explícito antes de publicarse (RN-PRC-001, RN-PRC-002).
- **Margen mínimo objetivo**: [[ COMPLETAR: definir con contabilidad — no
  hay un mínimo fijado aún; hasta entonces, todo precio bajo el margen del
  producto comparable más cercano requiere justificación escrita ]].
- Precio en POS (sucursal, kiosko, web) es fijo e innegociable; solo varía
  por lista de precios (RN-PRC-003). Fuera de POS (cotizaciones B2B/eventos)
  es negociable dentro de un rango que Comercial define caso a caso, sin
  bajar del margen mínimo sin aprobación de gerencia.
- La lista de precios la crea Comercial con asesoría de Contabilidad
  (RN-PRC-005); todo cambio de precio pasa por el SOP de evaluación de
  precio y margen, no se edita directo en el POS.
- Precio de producto nuevo lo estudian Comercial, Contabilidad e I+D+i
  (RN-PRC-002) — Comercial aporta el valor percibido y la competencia de
  mercado; Contabilidad el costo real; I+D+i la receta/costo de producción.

## 2. Ofertas y promociones

- Toda promoción la determinan Comercial, Marketing y Contabilidad
  (RN-PRM-001): comunicación, material, capacitación del personal, y
  duración definida — nunca "hasta que se acabe el interés".
- Debe estar en el guion de atención del personal antes de salir al público
  (RN-PRM-002) — una promoción que el personal no sabe explicar genera más
  fricción que ventas.
- Objetivos posibles de una promoción: lanzamiento de producto, fidelización,
  rotación de inventario (vencimiento próximo, sobre-stock), subir ticket
  promedio. Cada promoción declara cuál persigue — mide distinto según el
  objetivo.
- Toda promoción se liga a una lista de precios marcada `es_promocional` con
  fecha de inicio y fin en el ERP; al vencer, el precio regular se restaura
  automáticamente (no depende de que alguien "se acuerde" de apagarla).

## 3. Metas de venta e incentivos

No hay hoy un esquema de incentivo/comisión definido — se construye antes de
aplicarse, no se improvisa sobre la marcha:

- Toda meta de venta (monto, ticket promedio, unidades de un producto en
  impulso) se define por sucursal/canal con un periodo claro (semanal,
  mensual).
- Si se decide vincular la meta a un incentivo o comisión: el criterio lo
  aprueban **Comercial + RRHH + Gerencia** juntos (impacto en planilla y en
  clima laboral), se documenta por escrito, y se comunica al personal
  **antes** de empezar a medirse — nunca aplicado con efecto retroactivo.
- Hasta que exista ese criterio, las metas son de gestión (Comercial mide y
  ajusta operación) sin efecto en el sueldo del trabajador.

## 4. Evaluación de desempeño comercial del personal

Comercial mide desempeño de venta de forma **continua** (no solo en el
periodo de prueba): cumplimiento de guion, ticket promedio, quejas por
atención, tasa de desistimiento. Este dato es insumo para RRHH — la
decisión de continuidad laboral (periodo de prueba, renovación de contrato)
la sigue tomando RRHH con el administrador, según sus propios SOPs
([evaluacion-periodo-prueba](../diagrams/Procesos/Recursos-Humanos/Induccion/evaluacion-periodo-prueba.md)).
Comercial no cesa personal por su cuenta.

## 5. Coordinación con áreas que aún no tienen documentación propia

- **Marketing**: genera leads y material de campaña/promoción; Comercial
  define qué producto/oferta impulsar y a qué público. Sin doc de área
  propia todavía — el lado de Comercial vive en
  [coordinacion-marketing-leads](../diagrams/Procesos/Comercial/Metas-Desempeno/coordinacion-marketing-leads.md).
- **I+D+i / Producción**: desarrolla receta y viabilidad de producto nuevo;
  Comercial aporta mercado, público y expectativa de precio/margen. Sin doc
  de área propia todavía — el lado de Comercial vive en
  [coordinacion-desarrollo-nuevo-producto](../diagrams/Procesos/Comercial/Estrategia-Mercado/coordinacion-desarrollo-nuevo-producto.md).

## Referencias

- Reglas de negocio: RN-PRC-*, RN-PRM-*, RN-COM-*, RN-CML-* en [business-rules.md](../domain/business-rules.md)
- Glosario: Precio, Lista de Precios, Promoción, Margen de Contribución en [glossary.md](../foundation/glossary.md)
- SOPs del área: [docs/diagrams/Procesos/Comercial/](../diagrams/Procesos/Comercial/)
