# ADR-014 — Parámetros operativos configurables por empresa

- Estado: aceptado
- Fecha: 2026-07-27 (ampliada e implementada 2026-08-02, ver
  [Addendum](#addendum-2026-08-02--el-cambio-lo-propone-el-área-y-lo-aprueba-gerencia))

## Contexto

`ROADMAP.md` acumulaba una lista de "Pendientes de decisión" que en
realidad no eran preguntas de negocio sin resolver, sino valores que
**nunca deben fijarse una sola vez**: rango salarial de cada perfil de
puesto, margen de error de ajuste de inventario, monto del fondo de caja
chica de compras, plazo interno de envío de comprobantes al contador.
Redactarlos como texto
fijo en un documento de política (`[[ COMPLETAR ]]`) o hardcodearlos en
código habría significado tocar código o un documento cada vez que el
negocio los ajuste — y el usuario confirmó que sí van a variar: "no son
cosas fijas siempre".

> **Corrección (2026-08-01, ADR-019):** esta lista incluía además "frecuencia
> de conteo cíclico por categoría de insumo". No corresponde a
> `parametro_empresa`: el negocio precisó que la frecuencia la fija **cada
> categoría** y no hay un valor único por empresa, así que vive como columna
> `categoria.frecuencia_conteo`. `parametro_empresa` indexa por
> `(empresa_id, modulo, codigo)` — un valor por categoría obligaría a
> codificar el `categoria_id` dentro del `codigo` y perder la FK. El margen
> de error de ajuste de inventario, que sí es único por empresa, sigue en
> esta lista.

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

> ⚠️ **Revertido por el Addendum 2026-08-02**: `regla_aprobacion` fue
> retirada; `parametro_empresa` es la única tabla de configuración por
> empresa. El párrafo siguiente queda como registro de la decisión original.

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
`regla_aprobacion` (permiso ya eliminado con ella). Ninguna área
edita su propio parámetro por fuera de este mecanismo (mismo principio de
fuente única que RN-GER-003 aplica a la matriz de aprobaciones).

## Consecuencias

- Los "Pendientes de decisión" de `ROADMAP.md` referidos a valores
  operativos (rangos salariales, margen de error de
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
- ~~`parametro_empresa` **no está implementada todavía**~~ — implementada
  el 2026-08-02 junto con el flujo de aprobación del Addendum (modelo,
  migración `a71c9f4b2e60`, endpoints y tests). El permiso
  `gerencia.gestionar_parametros_empresa` sí quedó sembrado en
  `src/seeders/seed.py` (2026-07-27) adelantado a la entidad — mismo
  patrón que ya sigue `gestionar_reglas_aprobacion`: el catálogo RBAC no
  espera a que exista el caso de uso que lo consume, así el primer slice
  que implemente `parametro_empresa` no necesita tocar el seeder para
  autorizar su propio endpoint.
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

## Addendum 2026-08-02 — el cambio lo propone el área y lo aprueba Gerencia

El usuario precisó el modelo de gestión: **cada parámetro se configura
desde el módulo al que pertenece** (Compras propone su umbral de OC,
Almacén su margen de error de ajuste, RRHH sus rangos salariales), pero el
valor **no se modifica de verdad hasta que Gerencia lo aprueba** en su
sección de aprobaciones, donde puede **aceptar, rechazar o modificar**.
Recién aprobado, el cambio se refleja en los datos que el módulo consume.
Esto corrige el supuesto de la decisión original ("Gerencia es quien
carga el valor"): Gerencia gobierna, no digita.

**Cómo se implementó (sin tabla de solicitudes aparte)**: `estado`
(`propuesto` → `vigente` | `rechazado`, más `reemplazado`) sobre la propia
fila de `parametro_empresa`. Una propuesta es una fila más; la lectura
(`src/shared/parametros.py::valor_vigente`) solo devuelve `estado='vigente'`,
así que una propuesta pendiente es sencillamente **invisible** para el
módulo — ese es todo el mecanismo de "no surte efecto hasta aprobar", sin
código de gating. Aprobar marca la fila anterior como `reemplazado`; un
índice único parcial `WHERE estado='vigente'` impide dos valores vigentes.
"Modificar al aprobar" es un `valor` opcional en el body de `/aprobar`.

Consecuencias del addendum:

- **No hay `solicitud_cambio_parametro`**: una segunda tabla habría
  duplicado `empresa_id/modulo/codigo/valor` y obligado a copiar la fila
  aprobada de una a otra. Con estados en una sola tabla, el historial
  (quién propuso, quién resolvió, cuándo, valor anterior y nuevo) es la
  tabla misma — tampoco hace falta escribir en `audit_log`.
- **Un permiso por módulo para proponer** (`<modulo>.proponer_parametro`,
  catálogo en `src/shared/parametros.py::MODULOS`) más
  `gerencia.gestionar_parametros_empresa` para aprobar/rechazar/modificar.
  Como el permiso exigido depende del `modulo` del body, no puede
  resolverse en un `Depends`: el handler llama a `check_permission`. El
  `modulo` se valida como `Literal` en el schema, así un módulo inventado
  muere en el borde (422) en vez de mapear a un permiso inexistente.
  `MODULOS` usa el nombre del **módulo de código** (`accounting`, `sales`),
  no el del área (`contabilidad`, `comercial`) — los docs que mezclaban
  ambos se corrigieron.
- **`GET /parametros` sin filtro de `modulo` exige el permiso de Gerencia**:
  con `?modulo=X` basta el permiso de ese módulo. No todos los parámetros
  son inocuos — `rrhh/rango_salarial_*` no es de lectura general.
- **`decision_gerencial_id` descartado** (2026-08-02): el par
  propuesta/aprobación ya registra quién, qué, cuándo y con qué sustento
  (`motivo`); la FK duplicaba ese rastro. `decision_gerencial` sigue
  pendiente para su propio caso (OC escalada, campaña sobre presupuesto,
  sanción), no para parámetros. Esto **revierte** la previsión de la
  decisión original.
- **`regla_aprobacion` retirada** (2026-08-02, migración `b82d4c1f7a35`):
  esto **revierte** el "no se reemplaza ni se fusiona" de la decisión
  original. Con el flujo de aprobación ya construido, la razón para
  mantenerla desaparece: su único campo propio, `permiso_requerido`, era
  informativo. Sus filas vigentes se copiaron como parámetros
  `{"monto": ...}` ya aprobados y la tabla se borró.
  `src/shared/aprobaciones.py::umbral_vigente` sobrevive como envoltorio
  tipado (`Decimal`) sobre `parametro_empresa`, así `purchases`/`accounting`
  no cambiaron una línea.
- **La bandeja de Gerencia es un filtro, no una pantalla nueva de datos**:
  `GET /api/v1/parametros?estado=propuesto`. El frontend de cada módulo
  usa el mismo endpoint filtrando por `modulo` para mostrar el estado de
  lo que esa área propuso.
- **Un parámetro compuesto se lee con `valor_vigente`, no con
  `umbral_vigente`** (2026-08-06, primer caso): `inventory/
  margen_error_ajuste` es `{"porcentaje": 2, "piso": "20.00", "divisa":
  "PEN"}` — dos tolerancias en una fila, no un monto contra el cual
  comparar. `umbral_vigente` sigue siendo el atajo tipado para el caso
  escalar (`purchases/oc_umbral`, `accounting/pago_umbral`); el módulo que
  necesita más de un número desarma el dict él mismo y deja el default de
  `settings` como valor de arranque. No hace falta un envoltorio por forma:
  el contrato de la forma ya vive en `magnitudes.py` y en el seeder que
  propone el valor.

## Addendum 2026-08-02 (b) — toda magnitud lleva su unidad

El usuario cerró un hueco del addendum anterior: `valor` era JSONB de forma
libre, así que `{"monto": 2000}` pasaba. Un número suelto es ambiguo —¿soles
o dólares? ¿kilos o unidades?— y en un valor que Gerencia aprueba esa
ambigüedad se vuelve una decisión mal tomada. Además pidió que **la cantidad
de decimales sea configurable**, en la unidad de medida y en la divisa.

**Decisión** (RN-GER-010):

- Nueva entidad transversal **`divisa`** (`codigo`, `nombre`, `simbolo`,
  `decimales`, `activa`), sembrada con PEN/S/2. No cambia RN-PRC-004:
  `precio` sigue sin columna de divisa, la operación sigue siendo PEN única.
  La tabla existe para que un monto pueda **nombrar** su unidad y para que
  los decimales dejen de ser la constante 2.
- Nueva columna **`unidad_medida.decimales`** (default 3): Kilo necesita
  gramos, Unidad necesita 0.
- **`src/shared/magnitudes.py`**: contrato de forma del valor. Las claves
  `monto`/`minimo`/`maximo` exigen `divisa`; `cantidad` exige
  `unidad_medida_id`; incumplirlo es 409 —`MagnitudInvalida` hereda de
  `ReglaNegocio`, así que la traduce el handler global de
  `core/error_handlers.py` sin `try/except` por endpoint—; declarar una unidad sin su magnitud (o mezclar dinero
  con magnitud física) también falla. Lo adimensional (`porcentaje`, `dias`,
  `frecuencia`) pasa intacto y sin unidad.
- Nueva columna **`parametro_empresa.valor_display`** con la magnitud ya
  formateada ("S/ 2000.00", "5.000 Kilo"), que es lo que Gerencia lee al
  decidir. Se **congela con la fila**: renombrar la UdM el año que viene no
  reescribe lo que se aprobó.

**Por qué así**:

- **Sin tabla de "tipos de magnitud"**: las claves del propio JSON dicen qué
  es el valor. Un catálogo de tipos sería una indirección para no leer
  `"monto"`.
- **`magnitudes.py` no consulta catálogos**: recibe un `Unidad(decimales,
  etiqueta, prefija)` ya resuelto. Así `shared` no importa `inventory`; el
  caso de uso (`users.application.gerencia`) resuelve la divisa contra
  `shared.DivisaRepo` y la UdM contra el contrato público
  `inventory.application.queries_publicas` — el mismo patrón que
  `sales.queries_publicas`.
- **La misma validación al proponer y al modificar-y-aprobar**: si solo
  validara al proponer, Gerencia podría meter un monto sin divisa por la
  puerta de atrás.
- **Magnitudes como texto, no float**: `{"monto": "2000.00"}`. Un monto que
  pasa por float pierde centavos. `ROUND_HALF_UP`, no el `HALF_EVEN` por
  defecto de `Decimal`: en dinero el medio centavo sube.
- **La migración `c93e5a7b1d42` completa `divisa: PEN`** en los umbrales que
  venían de `regla_aprobacion` (que nunca tuvo divisa), para no dejar filas
  incumpliendo la regla que se acaba de escribir.

**Lo que NO se construyó** (y por qué): CRUD de `divisa` y de
`unidad_medida`. Hoy ninguna de las dos tiene endpoints — las filas salen
del seeder. `decimales` es configurable *en el dato*; editarlo desde la UI
llega con el slice de catálogo de `inventory` y con el de divisas si alguna
vez hay una segunda moneda. Construir dos CRUD ahora para un catálogo de una
fila (PEN) sería andamiaje sin usuario.
