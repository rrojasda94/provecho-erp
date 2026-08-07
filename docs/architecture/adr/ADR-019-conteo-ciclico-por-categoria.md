# ADR-019 — Conteo cíclico: frecuencia por categoría y programa derivado

- Estado: aceptado
- Fecha: 2026-08-01

## Contexto

`RN-INV-007` dice que "la periodicidad de conteos es configurable por el
ERP", sin decir dónde vive ese valor ni con qué forma. La política de
almacén (`docs/almacen-logistica/politica-almacen-logistica.md` §2) llevaba
dos `[[ COMPLETAR ]]` esperando esa definición, y ADR-014 había listado
"frecuencia de conteo cíclico por categoría de insumo" entre los candidatos
a `parametro_empresa`.

El negocio precisó el requisito: **la frecuencia la determina la categoría
a la que pertenece cada SKU** — diaria, semanal, quincenal, mensual,
semestral o anual — y **no existe un número universal**. Un perecible se
cuenta a diario y un abarrote al mes, en la misma empresa y el mismo
almacén. Además, si un conteo no se hace en su fecha, eso tiene que
reportarse a almacén y a gerencia.

Eso invalida la asignación que ADR-014 había anticipado:
`parametro_empresa` está indexada por `(empresa_id, modulo, codigo)` — un
valor por empresa. Meter ahí una frecuencia por categoría obligaría a
codificar el `categoria_id` dentro del `codigo`
(`frecuencia_conteo:<uuid>`), convirtiendo una FK en una cadena y dejando
la integridad referencial sin quien la haga cumplir: borrar una categoría
dejaría un parámetro huérfano que nada detecta.

## Decisión

**1. La frecuencia es una columna de `categoria`**, no un
`parametro_empresa`: `categoria.frecuencia_conteo` (enum `diario` |
`semanal` | `quincenal` | `mensual` | `semestral` | `anual`, nullable).
NULL deja la categoría fuera del ciclo — se cuenta solo si alguien abre un
conteo general o una auditoría. Es un atributo de la categoría, del mismo
modo que `articulo.controla_lote` es un atributo del artículo (ADR-015) y
no un parámetro global: pertenece a la entidad que describe, la FK la
protege, y se edita donde se administra la categoría
(`PATCH /inventory/categorias/{id}`, permiso `inventory.gestionar_catalogo`).

`parametro_empresa` sigue siendo el mecanismo correcto para lo que sí es
un valor único por empresa. El **margen de error del ajuste** (RN-INV-015)
es de esa clase. **Resuelto el 2026-08-06**: se lee de
`inventory/margen_error_ajuste` y `settings.inventory_margen_ajuste_pct`
(2 %) queda como default de arranque, no como la regla. El valor aprobado
lleva **porcentaje y piso en dinero** —la diferencia se valoriza al
`costo_promedio` del artículo y basta cumplir una de las dos tolerancias—,
y `dentro_margen` pasó a calcularse en el servidor también para el ajuste
ad-hoc, que hasta entonces lo recibía del cliente.

**2. El calendario se deriva, no se almacena.** No hay tabla
`programa_conteo`. La próxima fecha de una categoría en un almacén es el
último conteo **cerrado** que la cubrió, más los días de su frecuencia; si
nunca se contó, el reloj arranca en el alta de la categoría.

Una tabla de programación habría que mantenerla sincronizada con cada
conteo cerrado, cada alta de categoría, cada alta de almacén y cada cambio
de frecuencia — cuatro caminos de escritura para un dato que ya es una
función de otros dos. Lo derivado no se desincroniza. El costo es una
consulta por par (almacén × categoría) al pedir el programa, sobre tablas
de decenas de filas.

Un **conteo general** (`conteo.categoria_id` NULL) satisface a todas las
categorías de ese almacén: contó todo, sería absurdo que el programa
siguiera reclamando cada categoría por separado.

**3. La frecuencia se cuenta en días, no en meses de calendario.**
`mensual` son 30 días desde el último conteo, no "el mismo día del mes
siguiente". Es lo que el almacén hace en la práctica ("cada mes"), y evita
que el programa dependa de cuántos días tenga febrero. Si el negocio pide
anclar al día del mes, cambia la función de `domain/rules.py` y nada más.

**4. El conteo no toca el stock.** Al cerrarlo, cada diferencia genera un
`ajuste` en estado `pendiente` con `ajuste.conteo_id` apuntando al conteo
que la descubrió. Ese ajuste sigue exigiendo un aprobador distinto del que
contó (RN-INV-006) y es él quien mueve el stock. Sin ese enlace, un ajuste
nacido de un recuento sería indistinguible de uno pedido a mano y la
auditoría perdería el hilo.

**5. El stock esperado se congela al abrir**, no al cerrar. El almacén
sigue operando mientras se cuenta; medir lo contado contra un stock que se
movió durante el conteo inventa diferencias que nadie provocó. Es el mismo
criterio de "congelar el fondo" del arqueo de caja (PROC-CTB-005).

**6. Conteo a ciegas por defecto** (RN-INV-005): `GET /inventory/conteos/{id}`
omite `cantidad_sistema` y `diferencia` salvo que el usuario tenga
`inventory.ver_stock_esperado`. El rol `almacenero` cuenta sin verlo; el
`encargado` sí lo ve. Que el contador conozca el número esperado es la vía
más barata de que el conteo confirme el sistema en vez de auditarlo.

**7. Lo no contado en su fecha se reporta a almacén y gerencia**
(RN-INV-021): `POST /inventory/conteos/verificar-vencidos` publica
`inventory.conteo_vencido` por cada categoría atrasada, y
`GET /inventory/conteos/programa` muestra el estado (`al_dia` |
`vence_hoy` | `vencido`) con los días de atraso. El día en que vence
todavía no es falta — recién al día siguiente hay atraso.

## Consecuencias

- Los dos `[[ COMPLETAR ]]` de la política de almacén sobre periodicidad
  dejan de ser preguntas de documentación: la respuesta es "la que
  Gerencia cargue en cada categoría". Lo que queda es trabajo de
  configuración, no de código.
- ADR-014 pierde uno de sus cinco ejemplos. Se corrigió ahí mismo para que
  no queden dos documentos afirmando cosas distintas sobre dónde vive la
  frecuencia de conteo.
- La migración no rellena ninguna frecuencia: todas las categorías
  existentes quedan en NULL, es decir fuera del ciclo. Un valor por
  defecto inventado habría hecho aparecer conteos vencidos de la nada el
  día del despliegue.
- ~~`inventory.conteo_vencido` se publica pero **nadie lo consume
  todavía**.~~ **Resuelto 2026-08-06**: `users` lo pone en la bandeja del
  almacén y de gerencia (`destinatarios_de_almacen`), igual que
  `inventory.lote_vencido_detectado` (ADR-015). El endpoint del programa
  sigue siendo la vista completa; la notificación es el empujón.
- ~~El barrido de vencidos es **a demanda**, sin periódico que lo
  dispare.~~ **Resuelto 2026-08-06**: `inventory.reportar_conteos_vencidos`
  corre en Celery beat, diario a las 06:15 hora Perú. La premisa de este
  punto —"el proyecto no tiene Celery beat"— quedó falsa el 2026-08-04, con
  el barrido de pedidos demorados; sumarlo fueron dos entradas de
  `beat_schedule`, no infraestructura.
- El conteo no se replica al hub de sucursal (ADR-009): contar sin
  conexión no está cubierto. El hub replica stock para poder vender
  offline, no para auditar el almacén.

## Alternativas descartadas

- **Frecuencia en `parametro_empresa`** (lo que anticipaba ADR-014) —
  descartada por lo dicho en Contexto: un valor por empresa no modela un
  valor por categoría sin degradar una FK a texto dentro de `codigo`.
- **Frecuencia por artículo en vez de por categoría** — descartada: el
  usuario fue explícito en que el criterio es la categoría o lista a la
  que pertenece el SKU. Por artículo sería más fino y muchísimo más caro
  de mantener (cientos de artículos configurados a mano), y el artículo
  que necesita una periodicidad propia siempre puede mudarse a una
  categoría con esa frecuencia.
- **Tabla `programa_conteo` con la próxima fecha materializada** —
  descartada: cuatro caminos de escritura para mantener un dato derivable
  de dos. Se reevalúa si el programa llega a pesar en consulta, que con
  decenas de almacenes y categorías no ocurre.
- **Que cerrar el conteo aplique el ajuste directamente** — descartada:
  rompe la segregación de funciones de RN-INV-006. Quien cuenta detecta la
  diferencia; corregir el stock es otra firma.
- **Bloquear el cierre hasta contar todos los ítems** — descartada: un
  conteo parcial es legítimo (media hora antes de cerrar, solo la cámara
  de frío). Los ítems no contados se ignoran en vez de declararse
  faltantes, que es lo único peligroso que podía pasar.
