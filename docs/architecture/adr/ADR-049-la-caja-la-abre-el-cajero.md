# ADR-049 — La caja la abre el cajero; la firma queda donde la plata cambia de manos

- Estado: aceptado
- Fecha: 2026-08-15
- Enmienda: **ADR-025** (ciclo de caja completo), punto 3 de su decisión

## Contexto

ADR-025 decidió que «cada relevo lo firma quien recibe, con su PIN» y aplicó
esa idea a **tres** momentos: la apertura del turno, el cierre del turno y
cada tramo de `custodia_efectivo`. `POST /cajas/apertura` y
`POST /cajas/apertura/{id}/cierre` exigían, además del permiso de sesión
`accounting.caja_operar`, una elevación por PIN con `accounting.caja_relevar`
— permiso que el rol `cajero` **no tiene**. El dominio remataba con dos
candados: el firmante de la apertura no podía ser el propio cajero, y el
receptor del cierre tampoco.

El resultado en el local es el que informó el dueño del negocio: para
empezar su turno, el cajero necesitaba que un encargado caminara hasta la
caja a poner su PIN. Todos los días, en cada apertura. Lo que pasa cuando una
medida de control cuesta más que el riesgo que cubre ya se sabe: **la sesión
del encargado quedaba abierta en la caja**, disponible para cualquiera que
pasara. La firma que existía para probar quién tenía el efectivo terminó
produciendo exactamente el escenario que hace imposible probarlo.

Y no era una firma que probara mucho: al abrir, lo único que hay para
verificar es cuánto hay en el cajón, y eso lo prueba el **conteo por
denominación** (RN-POS-003), que ADR-025 ya había hecho obligatorio. La firma
del encargado no agregaba evidencia sobre el efectivo — agregaba una
presencia.

Había además una inconsistencia que este ADR destapa: como el cierre exigía
la firma del encargado, `custodia_efectivo` nacía directamente en
`en_supervisor`. El estado `en_caja` existía en la tabla de transiciones
desde el primer día y **el sistema no lo escribía nunca**. Un turno cerrado
a las 11 de la noche figuraba con el efectivo en manos del encargado aunque
la plata siguiera en el cajón hasta la mañana siguiente.

## Decisión

### 1. Abrir y cerrar el turno son actos del cajero, sin firma de nadie

Los dos endpoints exigen solo `accounting.caja_operar`. Se elimina la
elevación por PIN y el campo `autorizacion` de `AbrirCajaIn` y
`CerrarCajaIn`. Se eliminan los dos candados de dominio —«el encargado que
releva no puede ser el mismo cajero» y su gemelo en el cierre— porque sin
firmante no tienen sujeto.

Todo lo demás del cierre queda intacto: conteo por denominación, monto
esperado calculado contra los cobros reales (`total_efectivo_cobrado`),
cuadre de tarjetas contra el lote de cada POS operativo (RN-POS-004),
diferencia contra lo declarado sin bloquear (RN-POS-011), destino de
custodia y atribución del descuadre. Nada de eso dependía de la firma.

`apertura_caja.relevo_encargado_id` pasa a **NULLABLE** (migración
`c8b41f60d2a7`). No se borra: las aperturas anteriores sí tienen quién
firmó, y esa evidencia no se reescribe. Tampoco se rellena con el propio
cajero — «llenar» la columna al precio de inventar una contraparte es
justamente el dato falso que la firma existía para evitar.

### 2. El efectivo nace `en_caja`, a nombre del cajero

`custodia_efectivo` se crea en `en_caja` con `responsable_actual_id` = el
cajero, y su primer `timestamps_relevo` es el cierre. **Sin migración de
datos**: `en_caja` ya era el primer valor del enum y ya estaba en
`CUSTODIA_TRANSICIONES`; lo único que cambia es que ahora se escribe.

Esto tiene una consecuencia que vale más que la prolijidad: mientras nadie
firme, el responsable del faltante es el cajero (RN-MDP-005). Antes el
sistema declaraba entregado a las 23:00 lo que en la práctica se entregaba a
las 09:00 del día siguiente, y un faltante detectado en el medio le caía al
encargado por una firma que el software le había puesto solo.

También ensancha la ventana de corrección hacia el lado correcto: un cierre
se reabre mientras el efectivo siga en el local (`en_caja`/`en_supervisor`,
RN-MDP-005), y ahora recontar *mientras la plata sigue en el cajón* —el único
caso en que recontar prueba algo— pasó de ser un estado inalcanzable a ser el
caso normal.

### 3. La firma sobrevive donde sirve: la entrega

`POST /cajas/custodias/{id}/entregar` sigue exigiendo la elevación con
`accounting.caja_relevar` y pasa a ser el **único** punto del ciclo de caja
que la pide. Su primer tramo, `en_caja → en_supervisor`, es el que el
encargado firma cuando pasa a recoger el efectivo — puede ser una hora o
doce después del cierre, y esa distancia es un hecho del negocio que el
sistema ahora modela en vez de aplanar.

La segregación que importa queda intacta y es más nítida que antes: el
cajero **no puede** firmar que recibió su propia plata, porque su rol no
tiene `accounting.caja_relevar`. No hace falta un candado de dominio contra
relevarse a sí mismo; lo hace el permiso, que es donde corresponde.

## Alternativas descartadas

- **Darle `accounting.caja_relevar` al rol `cajero`.** Un renglón en el
  seeder y el problema desaparece. También desaparece la cadena de custodia:
  con ese permiso el cajero se firma a sí mismo la recepción del efectivo y
  todos los tramos quedan a su nombre. El costo de operación se resolvía
  destruyendo el control, no moviéndolo.
- **Mantener la firma solo en el cierre.** Es el momento donde hay más plata
  y suena al mejor compromiso, pero es justamente donde la firma era **más**
  falsa: el encargado firmaba recibir algo que se quedaba en el cajón hasta
  el otro día. Además, el cierre lo dispara el fin del turno, no la
  disponibilidad del encargado — obligar a que coincidan es cómo se llega a
  turnos que se cierran a la mañana siguiente.
- **Hacer `autorizacion` opcional en los dos endpoints.** Compatibilidad
  hacia atrás gratis, pero deja dos ciclos de caja conviviendo y ninguna
  respuesta a «¿este turno se abrió con firma o sin ella?» que no sea mirar
  fila por fila. Una regla con dos versiones simultáneas no es una regla.
- **Rellenar `relevo_encargado_id` con el cajero en vez de dejarlo NULL.**
  Evitaba la migración y mantenía `encargado_de_turno` devolviendo algo.
  Devolvía al cajero como encargado del local, que es falso, y le habría
  mandado a él los avisos que existen precisamente para que los atienda
  alguien con autoridad para resolverlos.

## Consecuencias

- **Contrato de API**: `AbrirCajaIn` y `CerrarCajaIn` pierden `autorizacion`
  (era requerido). `AperturaCajaOut.relevo_encargado_id` pasa a nullable.
  `openapi.json` regenerado.
- **`accounting.caja_relevar` deja de intervenir en abrir y cerrar.** Sigue
  siendo de `supervisor` y `contador`, y ahora describe una sola cosa:
  recibir efectivo.
- **`encargado_de_turno` (contrato público de `accounting`) se apaga en la
  práctica.** Salía del `relevo_encargado_id` de la caja abierta; con las
  aperturas nuevas devuelve `None`, y `reports` cae en su respaldo por rol
  (`supervisor`/`admin` de la sucursal, ADR-036) — que deja de ser la
  excepción y pasa a ser el camino normal. Sigue leyendo bien las aperturas
  viejas. Recuperar un encargado de turno de verdad necesita una fuente
  propia (un turno de personal, no la caja) y queda anotado como deuda.
- **`cierre_caja.relevos`** ya solo registra actos del cajero (el cierre y
  cada recuento tras una reapertura). El rastro de las entregas vive donde
  ocurren: `custodia_efectivo.timestamps_relevo`.
- **`accounting.cierre_caja_irregular`** mantiene `cerrado_por` —`reports` lo
  usa como `clave_actor`— y ahora vale el `cajero_id`: quien cerró el turno
  es él. El campo no se quita para no reescribir el catálogo de emisiones
  por un cambio de contenido.
- **Frontend**: los diálogos de apertura y cierre del PDV pierden el bloque
  de firma. El PDV queda con dos usos de `FirmaConPin` (consumo de personal
  y autorización de supervisor). `/contabilidad/caja` muestra el escalón
  `en_caja → en_supervisor`, que ya estaba escrito y nunca se había podido
  ver.
- **Lo que un encargado no puede hacer todavía**: ver la lista de turnos
  para recibir el efectivo. `GET /accounting/cajas/turnos` exige
  `accounting.leer`, que el rol `supervisor` no tiene, así que hoy firma la
  recepción sobre la pantalla de quien sí puede abrirla (que es como
  funciona toda elevación por PIN). Anotado como deuda — es un permiso, no
  un rediseño.
