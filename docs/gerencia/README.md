# Área Gerencia — Grupo Majambo

Gerencia es la capa de **autoridad, dirección estratégica y control** del
grupo. No ejecuta procesos operativos (los ejecutan las áreas); Gerencia
**decide, aprueba y supervisa**: fija el rumbo, es el último visado cuando
un área necesita aprobar una propuesta, y vela por que la empresa y los
trabajadores cumplan.

La ejerce el **Gerente General**, con facultades **delegadas por los
socios**. No confundir con los socios/dueños del grupo: las decisiones
reservadas a la sociedad (venta de propiedad intelectual, modificación de
marca, incorporación/salida de una empresa) no las toma Gerencia sola
(RN-GER-001).

Alcance documentado: **matriz de aprobaciones + gobierno corporativo**,
más un SOP de proceso: la **definición del presupuesto anual** (reunión
donde cada área presenta su propuesta y Gerencia designa presupuesto y
límites). La estrategia en sí se registra por decisión (acta), no por
procedimiento fijo.

## Qué hace Gerencia (y dónde vive)

| Responsabilidad | Dónde vive |
|---|---|
| Último visado de propuestas escaladas (qué requiere su aprobación, umbral, aprobador) | **Matriz de aprobaciones** → [politica-gerencia.md](politica-gerencia.md#matriz-de-aprobaciones) |
| Dirección estratégica: nuevos mercados, marcas, líneas de negocio | [politica-gerencia.md](politica-gerencia.md#dirección-estratégica) + [ficha-evaluacion-nuevo-mercado-marca](../templates/gerencia/ficha-evaluacion-nuevo-mercado-marca.md) |
| Presupuesto anual por área (reunión de propuestas + límites de gasto autónomo) | [Presupuesto/definicion-presupuesto-anual.md](../diagrams/Procesos/Gerencia/Presupuesto/definicion-presupuesto-anual.md) |
| Gobierno corporativo: delegación de facultades, conflicto de interés | [politica-gerencia.md](politica-gerencia.md#gobierno-corporativo) |
| Supervisión y control de cumplimiento; acción correctiva/disciplinaria | [politica-gerencia.md](politica-gerencia.md#supervisión-y-control) — Gerencia decide, el área competente ejecuta |

## Qué NO hace Gerencia (no duplica)

- **No ejecuta la sanción**: la decide/ordena, pero RRHH la aplica con el
  debido proceso (RN-RRHH-004, RN-GER-005).
- **No define el umbral de cada área por separado**: la matriz de
  aprobaciones es la fuente única; las áreas la referencian (RN-GER-003).
- **No reemplaza el estudio técnico**: decide con el sustento que
  producen Comercial (estudio de mercado) y Contabilidad (viabilidad
  económica), no por intuición (RN-GER-006).
- **No toma decisiones de socios**: PI, marca, alta/baja de empresa
  (RN-GER-001).

## Documentos del área

| Documento | Contenido |
|---|---|
| [politica-gerencia.md](politica-gerencia.md) | Gobierno corporativo, matriz de aprobaciones, dirección estratégica, supervisión y control |
| [perfiles/gerente-general.md](perfiles/gerente-general.md) | Perfil del puesto (misión, funciones, facultades delegadas) |
| [../templates/gerencia/](../templates/gerencia/) | Acta de decisión gerencial, evaluación de nuevo mercado/marca, propuesta de presupuesto anual |
| [propuesta-parametros-operativos.md](propuesta-parametros-operativos.md) | Los 13 valores propuestos para `parametro_empresa` (2026-08-05) con su sustento, qué pasa si están mal y cuándo revisarlos — pendientes de aprobación en `/gerencia/parametros` |
| [../diagrams/Procesos/Gerencia/](../diagrams/Procesos/Gerencia/) | SOP de definición del presupuesto anual |

## Principios del área

- **Toda decisión se documenta** (RN-GER-002): aprobación, rechazo o
  directiva quedan en un acta con quién, qué, cuándo y sustento — una
  decisión verbal no tiene validez operativa.
- **La autoridad es delegada, no absoluta**: el Gerente General responde
  ante los socios y respeta los límites de sus facultades.
- **Sin trato preferente ni conflicto de interés** (RN-GER-004, alinea
  RN-GRP-001): quien tiene interés en una propuesta se abstiene.
- **Decide con datos**: el sustento (mercado, viabilidad, evaluación del
  área) es requisito, no adorno.

## Referencias

- Reglas de negocio: RN-GER-*, y las que Gerencia aprueba (RN-CMP-008/015, RN-CML-003, RN-EMP-006, RN-GRP-006, RN-MAR-004) en [business-rules.md](../domain/business-rules.md)
- Glosario: Gerencia/Directivo, Gerente General, Socio, Matriz de aprobaciones, Acta de decisión gerencial en [glossary.md](../foundation/glossary.md)
- Autorización (RBAC): la facultad de aprobar es un permiso de rol, ver [authorization.md](../security/authorization.md)
