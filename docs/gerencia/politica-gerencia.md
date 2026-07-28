# Política de Gerencia — Grupo Majambo

Referencia de gobierno y autoridad del grupo. Donde un umbral o cifra no
está definido, se marca `[[ COMPLETAR ]]`.

## Gobierno corporativo

- **Facultades delegadas.** El Gerente General ejerce por delegación de
  los socios (glosario: *Gerencia/Directivo* vs. *Socio*). Puede
  autorizar contratos, gastos y sanciones dentro de los límites de la
  matriz de aprobaciones; fuera de esos límites, escala a los socios.
- **Decisiones reservadas a la sociedad** (RN-GER-001, no las toma
  Gerencia sola):
  - Venta de propiedad intelectual del Grupo (RN-GRP-006, aprobación
    unánime de socios).
  - Modificación de una marca — identidad, carta, procesos (RN-MAR-004,
    vía área de manejo de marca).
  - Incorporación o salida de una empresa del Grupo (RN-EMP-001).
- **Conflicto de interés** (RN-GER-004). Un directivo con interés
  personal o parte relacionada en una propuesta se abstiene de aprobarla
  y deriva la decisión a otro nivel. Alinea con RN-GRP-001 (ninguna
  empresa/persona recibe trato preferente en perjuicio de otra).
- **Toda decisión se documenta** (RN-GER-002). Aprobación, rechazo o
  directiva se registran en un **acta de decisión gerencial** (quién
  decide, qué, cuándo, sustento, condiciones), archivada en el ERP. Una
  decisión verbal no tiene validez operativa.

## Matriz de aprobaciones

Fuente **única** de qué requiere visado gerencial, su umbral y el
aprobador (RN-GER-003). Ninguna área fija un umbral propio por fuera de
esta tabla; los SOPs de cada área la referencian en vez de redefinirla.
Los umbrales cuantitativos (montos) viven como filas de la tabla
`regla_aprobacion` (editable por empresa vía
`gerencia.gestionar_reglas_aprobacion`, ver `data-model.md` §8c) — esta
tabla es la narrativa de gobierno (qué, quién, por qué), no el valor exacto.

| Qué se aprueba | Umbral / condición | Aprobador | Regla / fuente |
|---|---|---|---|
| Presupuesto anual de cada área | Una vez al año, en la reunión de presupuesto | Gerencia sobre propuesta del área e informe de Contabilidad | RN-GER-007 |
| Gasto de un área durante el año | Fuera de lo presupuestado, o sobre el límite de gasto autónomo del área `[[ COMPLETAR: límite por área ]]` | Gerencia (puntual) | RN-GER-007 |
| Contratación de agencia (servicio) | Marketing evalúa; excede el presupuesto/límite o requiere validación | Marketing evalúa + Gerencia valida | RN-MKT-006 |
| Orden de compra sobre umbral | Monto ≥ el configurado en `regla_aprobacion` (`purchases`/`oc_umbral`) por empresa — valor semilla S/2000 si nadie lo configuró aún; prohibido fraccionar para evadirlo | Administrador/Gerencia | RN-CMP-008 |
| Compra de activo / equipamiento | Siempre (cotización comparativa de ≥2 proveedores) | Área solicitante + Gerencia | RN-CMP-015 |
| Préstamo de una empresa | Siempre, con estudio de viabilidad previo | Gerencia sobre informe de Contabilidad | RN-EMP-006 |
| Esquema de incentivo/comisión de metas de venta | Al crearse o cambiar; nunca retroactivo | Comercial + RRHH + Gerencia | RN-CML-003 |
| Lanzamiento de nuevo producto (impacto/inversión mayor) | Cuando supera el criterio comercial normal `[[ COMPLETAR: definir cuándo escala a Gerencia ]]` | Gerencia sobre evaluación de Producción/I+D+i y Comercial | RN-PRD-017, RN-CML-005 |
| Entrada a nuevo mercado / marca / línea de negocio | Siempre | Gerencia (o socios si implica nueva empresa/marca) | RN-GER-006, RN-GER-001 |
| Acción correctiva/disciplinaria a un trabajador | Cuando la situación lo amerita | Gerencia decide; RRHH ejecuta | RN-GER-005, RN-RRHH-004 |
| Ajuste de inventario fuera de margen | Diferencia excede el margen acordado (valor en `parametro_empresa`, `inventory/margen_error_ajuste`) | Escala a administrador/Gerencia | RN-INV-015 |
| Rango salarial de un perfil de puesto | Al crear/actualizar el perfil | Administración/Gerencia | `parametro_empresa`, `rrhh/rango_salarial_<perfil>` (RN-GER-008) |

> Al agregar un nuevo punto de aprobación en cualquier área, se agrega
> aquí en el mismo cambio — no se documenta el umbral solo en el SOP del
> área.

## Parámetros operativos configurables

Distinto de la matriz de aprobaciones (arriba): esto no es "qué requiere
visado", es cualquier valor operativo que varía por empresa o en el
tiempo y que antes se documentaba como `[[ COMPLETAR ]]` fijo. Se
configura en `parametro_empresa` (RN-GER-008, `data-model.md` §8c,
ADR-014) — lo gestiona Gerencia, no cada área por su cuenta. Un cambio
puede sustentarse en un acta (`decision_gerencial`) cuando el ajuste lo
amerite — por ejemplo, tras una reunión con las cabezas de área — pero no
es obligatorio para un ajuste rutinario.

Primeros candidatos a configurar (mecanismo ya decidido; **valor real
pendiente de que Gerencia lo cargue**, no bloquea código):

| Parámetro | Módulo/código | Notas |
|---|---|---|
| Rango salarial por perfil de puesto (7 perfiles) | `rrhh/rango_salarial_<perfil>` | `{"minimo":..., "maximo":...}` |
| Frecuencia de conteo cíclico y de conteo general | `inventory/frecuencia_conteo_<categoria>` | `{"frecuencia":"diario"\|"semanal"\|"mensual"\|"anual"\|"fecha_especifica"}`, puede variar por categoría de insumo y por almacén |
| Margen de error de ajuste de inventario | `inventory/margen_error_ajuste` | `{"porcentaje":...}`, puede variar por tipo de producto |
| Monto del fondo de caja chica de compras | `purchases/monto_caja_chica` | `{"monto":...}`; el mecanismo de reposición ante faltante sigue siendo una decisión de proceso aparte, no solo de valor |
| Plazo interno de envío de comprobantes al contador | `contabilidad/plazo_envio_comprobante` | `{"dias":...}` |
| Margen de contribución mínimo objetivo | `comercial/margen_minimo` | `{"porcentaje":...}` |

Quedan **fuera** de `parametro_empresa` por ser decisiones de rol, no de
valor: quién autoriza ajustes de inventario (¿admin o un rol de
"supervisor de logística" que hoy no existe formalmente?) y el aprobador
suplente de OC en ausencia del administrador — ambos siguen pendientes en
"Pendientes de decisión" (`ROADMAP.md`).

## Dirección estratégica

- **Rumbo del grupo.** Gerencia define objetivos y direcciona el
  crecimiento (alinea responsabilidades del Grupo en
  [vision.md](../foundation/vision.md#organización)).
- **Nuevo mercado / marca / línea** (RN-GER-006). Requiere estudio previo
  documentado antes de decidir: estudio de mercado (Comercial,
  [investigacion-mercado-publico-objetivo](../diagrams/Procesos/Comercial/Estrategia-Mercado/investigacion-mercado-publico-objetivo.md))
  + viabilidad económica (Contabilidad, mismo principio que el estudio de
  préstamo RN-EMP-006). Gerencia decide con sustento, no por intuición;
  la decisión queda en acta. Formato de entrada:
  [ficha-evaluacion-nuevo-mercado-marca](../templates/gerencia/ficha-evaluacion-nuevo-mercado-marca.md).
- **Límite de socios.** Si la expansión implica una nueva empresa, una
  nueva marca del holding o venta/cesión de PI, la decisión final es de
  los socios (RN-GER-001), no de Gerencia.

## Presupuesto anual

- El presupuesto de cada área se define **una vez al año** en una reunión
  de presupuesto: cada área presenta su propuesta y Gerencia designa el
  presupuesto del año (RN-GER-007) — ver
  [definicion-presupuesto-anual](../diagrams/Procesos/Gerencia/Presupuesto/definicion-presupuesto-anual.md).
- Gerencia fija por área un **límite de gasto autónomo**: dentro del
  presupuesto y bajo el límite, el área ejecuta sin aprobación puntual;
  sobre el límite o fuera de lo presupuestado, aprueba Gerencia — así se
  evita aprobar caso por caso sin perder control. Límites por área
  `[[ COMPLETAR: definir en la reunión anual ]]`.

## Supervisión y control

- Gerencia vela por que la empresa y los trabajadores cumplan su trabajo
  y las reglas del grupo. Recibe las alertas que el ERP escala a nivel
  gerencial (cierre de caja irregular RN-MDP-005, ajuste fuera de margen
  RN-INV-015, reincidencia de no conformidad de producción RN-PRD-014,
  reportes de escalamiento no resueltos RN-CTP-004).
- **Acción correctiva** (RN-GER-005). Cuando la situación lo amerita,
  Gerencia decide/ordena la acción; **la ejecución formal la hace el área
  competente con su debido proceso**:
  - Sanción a un trabajador → RRHH (amonestación/memorándum con derecho a
    descargo, RN-RRHH-004). Gerencia no aplica la sanción por sí misma
    saltando el proceso.
  - Corrección de un proceso → el área dueña ajusta su SOP/regla.
- **Auditoría.** Toda auditoría a empresas del Grupo se hace con la misma
  profundidad, sin excepciones (RN-GRP-003).

## Referencias

- Reglas de negocio: RN-GER-*, RN-GRP-*, RN-EMP-006, RN-MAR-004, RN-CMP-008/015, RN-CML-003, RN-MKT-006, RN-PRD-017, RN-INV-015, RN-RRHH-004 en [business-rules.md](../domain/business-rules.md)
- Glosario: Gerencia/Directivo, Gerente General, Socio, Matriz de aprobaciones, Acta de decisión gerencial en [glossary.md](../foundation/glossary.md)
- Modelo de negocio y organización: [vision.md](../foundation/vision.md)
