# Área Producción — Grupo Majambo

**Spec a futuro (2026-07-20):** documentada antes de existir físicamente.
La primera **cocina de producción** está planeada para 2027; hasta
entonces toda la producción se hace dentro de las cocinas de sucursal
(personal y proceso ya cubiertos por `docs/rrhh/perfiles/` y por
Operaciones). Este documento y sus SOPs son la especificación con la que
se diseña la cocina de producción — no un proceso operando hoy.

Responsable de producir **subrecetas** (masa, salsa madre, bases) y
procesar insumos en **lotes de producción**, bajo control riguroso de
inocuidad y calidad — de la cocina de producción depende gran parte de la
calidad final del producto que llega al cliente. También es responsable
de la cocina de producción como espacio físico (mantenimiento, higiene),
de producir según cronograma + necesidades de Almacén Central, de dar
soporte técnico a I+D+i y Comercial para desarrollo de nuevo producto y
mejora continua, y de su propio inventario (similar al de Almacén
Central, mismo esquema de conteo cíclico).

No duplica lo que ya vive en otras áreas:

- **Recetas/subrecetas como concepto de dominio** (qué es una subreceta,
  cómo descuenta insumos) → ya modelado en
  [domain-model.md](../domain/domain-model.md#subreceta) y
  [business-rules.md](../domain/business-rules.md#productos-y-recetas)
  (RN-PRD-001 a 010).
- **Higiene/inocuidad de la cocina como espacio** (plaga, bioseguridad,
  devolución de sobrantes) → ya cubierto en
  [business-rules.md](../domain/business-rules.md#cocina-de-producción)
  (RN-CDP-001 a 004).
- **Evaluación de viabilidad de nuevo producto** (formato de la ficha) →
  vive en
  [Comercial/ficha-requerimiento-nuevo-producto.md](../templates/comercial/ficha-requerimiento-nuevo-producto.md);
  Producción la completa, no la posee.

Este README y sus SOPs cubren lo que faltaba: cronograma de producción
(fijo + ajuste por necesidad), control de calidad y manejo de no
conformidad, costeo real automático (insumos + mano de obra +
desperdicio por tipo), inocuidad (incluye temperatura de equipos de
frío), inventario propio de la cocina de producción, y el soporte
técnico que Producción brinda a I+D+i/Comercial.

## Flujo por responsabilidad

| Responsabilidad | Dónde vive |
|---|---|
| Plan de producción (cronograma fijo + ajuste por pedido urgente de Almacén) | [Planificacion/](../diagrams/Procesos/Produccion/Planificacion/) |
| Control de calidad, no conformidad (reproceso o desecho con evidencia) | [Calidad-Inocuidad/](../diagrams/Procesos/Produccion/Calidad-Inocuidad/) |
| Inventario de la cocina de producción (conteo cíclico, mismo esquema que Almacén Central) | [Inventario-Cocina/](../diagrams/Procesos/Produccion/Inventario-Cocina/) |
| Soporte técnico a I+D+i/Comercial (viabilidad de nuevo producto, mejora continua de receta) | [Soporte-IDI/](../diagrams/Procesos/Produccion/Soporte-IDI/) |

## Documentos del área

| Documento | Contenido |
|---|---|
| [politica-produccion.md](politica-produccion.md) | Cronograma, control de calidad/no conformidad, inocuidad (referida), inventario de cocina, soporte a I+D+i |
| [perfiles/](perfiles/) | Jefe de cocina (producción), cocinero de producción |
| [../templates/produccion/](../templates/produccion/) | Orden de producción, reporte de producción, ficha de no conformidad, checklist de inocuidad, reporte de conteo de cocina |

## Principios del área

- **Metódica y homologada**: mismo estándar de proceso en todas las
  cocinas de producción del grupo, sin variación por local.
- **La inocuidad no se negocia**: ante duda de higiene/plaga/bioseguridad,
  la operación se detiene (RN-CDP-002) antes que arriesgar el producto.
- **Ninguna no conformidad queda sin registro** (RN-PRD-014): se corrija o
  se deseche, siempre genera reporte de escalamiento con evidencia si hay
  destrucción (RN-PRD-015) — previene tanto mala calidad como robo
  disfrazado de merma.
- **El cronograma se cumple, con margen para lo urgente**: plan fijo por
  tipo de receta (evita contaminación cruzada, RN-PRD-012) más ajuste por
  necesidad real de Almacén, nunca al revés.
- **El costo real lo calcula el ERP, nunca a mano** (RN-PRD-018): insumos
  consumidos + mano de obra, con el desperdicio de cada insumo (tipo y
  peso) registrado y contrastado contra lo esperado en su receta.
- **Ningún reporte se transcribe a mano**: el reporte de conteo y el de
  producción se generan automáticamente desde lo ya registrado en el ERP
  (balanza, QR, horas-hombre) — el jefe de cocina visa, no redacta.
- **Equipo de frío fuera de rango no espera**: alerta automática a
  Gerencia apenas se registra la temperatura (RN-CDP-005), mismo criterio
  que la falla de frío en apertura de sucursal.
- **Nunca despacha directo a sucursal** (RN-CDP-001) — solo a Almacén
  Central.
- **Producción no lanza producto solo**: evalúa viabilidad técnica, pero
  la decisión de lanzamiento es de Comercial con la evaluación de
  Producción/I+D+i como insumo obligatorio (RN-PRD-017).

## Referencias

- Reglas de negocio: RN-PRD-*, RN-CDP-*, RN-VNC-*, RN-INV-017/018 en [business-rules.md](../domain/business-rules.md)
- Glosario: Cocina de Producción, Jefe de Cocina, Reporte de Producción, Subreceta, Lote en [glossary.md](../foundation/glossary.md)
- SOPs del área: [docs/diagrams/Procesos/Produccion/](../diagrams/Procesos/Produccion/)
- Spec técnica del módulo: [src/modules/production/README.md](../../src/modules/production/README.md)
