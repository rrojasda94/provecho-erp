# ADR-014 — Parámetros operativos configurables por empresa

- Estado: aceptado
- Fecha: 2026-07-27

## Contexto

`ROADMAP.md` acumulaba una lista de "Pendientes de decisión" que en
realidad no eran preguntas de negocio sin resolver, sino valores que
**nunca deben fijarse una sola vez**: rango salarial de cada perfil de
puesto, frecuencia de conteo cíclico por categoría de insumo, margen de
error de ajuste de inventario, monto del fondo de caja chica de compras,
plazo interno de envío de comprobantes al contador. Redactarlos como texto
fijo en un documento de política (`[[ COMPLETAR ]]`) o hardcodearlos en
código habría significado tocar código o un documento cada vez que el
negocio los ajuste — y el usuario confirmó que sí van a variar: "no son
cosas fijas siempre".

Ya existe precedente para esto: `regla_aprobacion` (`ADR` implícito en su
propio docstring, ver `data-model.md` §8c) generaliza el umbral de
aprobación de OC y de pago a proveedor como filas configurables por
empresa, gestionadas por Gerencia. Pero su esquema (`umbral: Decimal` +
`permiso_requerido`) asume que todo valor configurable es un monto que
gatilla una aprobación — no sirve para un rango salarial (necesita
mínimo y máximo), una frecuencia (`diario`/`semanal`/`mensual`/`anual`/
fecha específica, no un número), o un plazo en días. Extender
`regla_aprobacion` a la fuerza para estos casos habría forzado columnas
opcionales sin sentido (`umbral` no aplica a una frecuencia) o un
`permiso_requerido` ficticio para valores que no requieren aprobación de
nadie, solo configuración.

## Decisión

**Nueva entidad transversal `parametro_empresa`** (vive en `src/shared/`,
mismo criterio que `Comprobante`/`regla_aprobacion`/`decision_gerencial`):
`empresa_id`, `modulo`, `codigo`, `valor` (JSONB de forma libre por
código), `decision_gerencial_id` (FK opcional), `vigente`,
`vigente_desde`. El valor JSONB es la diferencia clave frente a
`regla_aprobacion`: permite `{"minimo":1500,"maximo":2200}`,
`{"frecuencia":"mensual"}`, `{"dias":5}` o `{"monto":500}` bajo el mismo
mecanismo, sin forzar un esquema numérico único.

`regla_aprobacion` **no se reemplaza ni se fusiona** — sigue siendo la vía
específica para umbrales que gatillan una aprobación (tiene
`permiso_requerido` con significado real, y ya está implementada y en uso
por `purchases`/`accounting`). `parametro_empresa` cubre todo lo demás:
cualquier valor operativo configurable por empresa, requiera o no
aprobación de por medio. RN-GER-008 (`business-rules.md`) documenta la
distinción.

**Sustento vía acta, no como requisito bloqueante**: `decision_gerencial_id`
es opcional. Un ajuste rutinario (ej. subir el margen de error de ajuste
de 2% a 3% porque la operación lo pidió) no necesita un acta — pero un
cambio con impacto real (ej. redefinir el rango salarial completo de un
perfil, tras una reunión con las cabezas de área) sí puede vincularse a un
`decision_gerencial` (que materializa el acta, RN-GER-002) como evidencia
de qué se decidió y por qué. El campo existe para cuando el negocio quiera
dejar ese rastro, no para forzarlo siempre.

**Quién lo gestiona**: Gerencia, vía permiso nuevo
`gerencia.gestionar_parametros_empresa` — mismo patrón de autorización que
`regla_aprobacion` (`gerencia.gestionar_reglas_aprobacion`). Ninguna área
edita su propio parámetro por fuera de este mecanismo (mismo principio de
fuente única que RN-GER-003 aplica a la matriz de aprobaciones).

## Consecuencias

- Los "Pendientes de decisión" de `ROADMAP.md` referidos a valores
  operativos (rangos salariales, frecuencia de conteo, margen de error de
  ajuste, monto de caja chica, plazo de envío de comprobantes) dejan de
  ser preguntas abiertas de arquitectura: el mecanismo está decidido. Lo
  que queda pendiente es que Gerencia cargue el valor real de cada uno
  cuando corresponda — trabajo de configuración/negocio, no de código ni
  de documentación.
- Dos entidades transversales de configuración con forma distinta
  (`regla_aprobacion` con `umbral: Decimal`, `parametro_empresa` con
  `valor: JSONB`) en vez de una sola — aceptado: forzar un solo esquema
  para "umbral de aprobación" y "rango salarial" habría sido peor que dos
  tablas con responsabilidad clara. Si en el futuro `regla_aprobacion`
  necesita más de un campo numérico (ej. un umbral con rango), se
  reevalúa fusionarlas.
- `parametro_empresa` **no está implementada todavía** — es spec (esta
  ADR + `data-model.md` §8c + RN-GER-008). Implementación queda en
  `ROADMAP.md` → Deuda técnica → Transversal, para cuando el primer
  parámetro real (candidato: rango salarial de RRHH) lo necesite en
  código.
- Sigue sin resolverse **quién autoriza** ciertas acciones (ej. ajuste de
  inventario fuera de margen: admin vs. un rol de "supervisor de
  logística" que hoy no existe formalmente) — eso es una decisión de rol
  (RBAC), no un valor de `parametro_empresa`, y queda fuera del alcance de
  esta ADR.

## Alternativas descartadas

- **Extender `regla_aprobacion` con un `valor: JSONB` opcional además de
  `umbral: Decimal`** — descartada: mezclar dos formas de valor en la
  misma tabla (una tipada, una libre) para casos de uso distintos
  (aprobación vs. configuración general) confunde más de lo que ahorra;
  el propio nombre de la entidad ("regla de aprobación") dejaría de
  describir lo que guarda.
- **Config por archivo/env var, editable solo por quien despliega** —
  descartada: el usuario fue explícito en que estos valores los define
  Gerencia dentro del ERP, no un archivo de configuración que solo alguien
  con acceso al servidor puede tocar. Rompe además el principio de
  multi-empresa (un `.env` es global al deploy, no por `empresa_id`).
- **Un `decision_gerencial` obligatorio por cada cambio de parámetro** —
  descartada: exigir un acta para subir en 0.5% un margen de error
  convertiría el ajuste rutinario en un trámite. El acta queda disponible
  para cuando el negocio decida que ese cambio la amerita, no como
  bloqueo universal.
