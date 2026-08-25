# ADR-039 — Rastro jerárquico y "volver" histórico

- Estado: aceptado
- Fecha: 2026-08-12

## Contexto

Cada ficha del back-office cableaba a mano su propio enlace de salida:
`← Artículos`, `← Recetas`, `← Jornada`, nueve en total. Dos problemas, y el
usuario reportó los dos en una frase — *"al retroceder sube de nivel, mas no
regresa a la pantalla anterior de la cual se procedía"*:

1. **Siempre subían un nivel.** Desde la ficha de un SKU, `← Artículos` lleva
   al listado aunque uno haya llegado desde la ficha del artículo. Desde una
   receta abierta con el enlace "editar" de un producto, `← Recetas` lleva al
   listado de recetas y no al producto del que se venía. El enlace contestaba
   "¿qué hay encima?" cuando la pregunta era "¿de dónde vengo?".
2. **No decían dónde estaba uno.** El sidebar marca la sección activa, pero la
   ficha no aparece en él: de un SKU no se sabía a qué artículo pertenecía.

`components/ui/breadcrumb.tsx` estaba instalado desde el rediseño (ADR-037) y
no lo usaba ninguna pantalla.

## Decisión

### 1. Son dos controles porque son dos preguntas

`<Rastro>` renderiza **el rastro jerárquico** (Inicio / Módulo / Sección / lo
que se ve) y, al lado, **un `←` histórico**. No se unificaron a propósito:

- El rastro contesta *dónde estoy*, y para una misma ruta es siempre el mismo
  camino. Es estable, se puede leer de un vistazo y cada nivel es clickeable.
- El `←` contesta *cómo deshago el último paso*, y depende de por dónde vino
  el usuario. No hay forma de que un solo control conteste las dos.

El `←` que hacía de las dos cosas es justamente lo que se rompía.

### 2. El rastro se **deriva** de la ruta

`rastroDe(pathname, hoja?)` (`lib/rastro.ts`) resuelve módulo y sección contra
`MODULOS` y `SUBMENUS` — los mismos dos registros que ya alimentan el home, el
sidebar y la paleta de comandos. Ningún nivel se escribe a mano; solo la
**hoja** la pasa la pantalla, porque un id no es un nombre.

Tres detalles que la implementación tuvo que resolver y que las pruebas fijan:

- **El módulo se identifica por el primer tramo de la ruta**, no por su
  `href`: el `href` de un módulo es su *primera pantalla*
  (`/inventario/articulos`), así que comparar contra él dejaba a
  `/inventario/lotes` sin módulo y el rastro quedaba en "Inicio".
- **Gana la sección con el prefijo más largo**, no la primera que coincide:
  `/contabilidad` es prefijo de `/contabilidad/caja`, y con la primera toda
  pantalla de contabilidad diría "Asientos".
- **Una sección que es la pantalla de entrada del módulo no se repite**:
  Inventario abre en Artículos, y dos migas seguidas al mismo destino no
  informan nada.

Función pura y sin React: lo que hay que poder probar es la resolución de la
ruta, no el dibujo (`lib/rastro.test.ts`).

### 3. El `←` es un enlace real que a veces prefiere el historial

Es un `<Link href={padre}>`: sin JavaScript, o con una entrada directa por
URL, navega al nivel de arriba —el comportamiento de antes, que como *fallback*
es correcto—. Cuando hay historial propio, intercepta el click y hace
`router.back()`.

**Cómo se sabe que hay historial propio: contándolo.** No hay de dónde leerlo,
y esto se midió en el navegador antes de decidirlo:

| Señal | Por qué no sirve |
|---|---|
| `window.history.state.idx` | En Next 16 App Router el estado solo trae `__NA` y el árbol interno. No hay índice. |
| `document.referrer` | Vacío en navegaciones blandas, que dentro del shell son todas. |
| `window.history.length` | Incluye lo que el usuario hizo antes de entrar al ERP. |

Así que `lib/historial.ts` lleva un contador de módulo que un
`<RastreoDeNavegacion />` montado **una sola vez** en el layout de `(app)`
incrementa con cada cambio de ruta. Módulo y no estado de React porque tiene
que sobrevivir al montaje y desmontaje de cada pantalla; montado en el layout
y no en la ficha porque lo que hay que saber es qué pasó **antes** de llegar a
la ficha.

Se reinicia con una recarga dura, y ahí el `←` cae al padre. Es conservador a
propósito: después de un F5 no sabemos qué hay detrás.

### 4. El rastro lo ponen las fichas, no el shell

`ModuloShell` no lo renderiza porque el shell no conoce la hoja, y hacérsela
llegar desde la pantalla exigiría un contexto cliente atravesando el layout
para un dato que la pantalla ya tiene en la mano.

Las **listas** tampoco lo llevan: el ítem activo del sidebar ya contesta dónde
está uno, que es el criterio que ADR-013 §8 fijó para el shell. El rastro
aporta el nivel que el sidebar no puede mostrar —la ficha— y por eso vive
donde ese nivel existe.

## Alternativas descartadas

- **Solo arreglar el `←` con `router.back()`**: quita el síntoma y deja la
  pantalla sin decir dónde está parado uno, que era la mitad del reporte.
- **Solo el breadcrumb**: el rastro es jerárquico por definición, así que
  clickearlo sigue subiendo de nivel — el síntoma reportado quedaba igual.
- **`router.back()` sin fallback**: con una entrada directa por URL —un enlace
  compartido, una pestaña nueva, un reporte que apunta a la ficha— el botón no
  hace nada o saca al usuario del ERP.
- **Derivar la hoja de la URL** (el último tramo): es un uuid.
- **Un contexto cliente para que el shell reciba la hoja**: plomería que
  atraviesa dos layouts para mover un string que la pantalla ya tiene.

## Consecuencias

- Nueve `← Sección` cableados a mano se reemplazan por `<Rastro hoja=… />`.
  Una pantalla nueva no vuelve a decidir a dónde va su salida.
- `<Rastro volverA>` existe para el único caso donde el padre no alcanza: la
  ficha de venta vuelve a la jornada **de su sucursal y su fecha**, que sin
  los query params se abriría en el día de hoy.
- El PDV y el KDS **no lo usan**: viven fuera de `(app)`, son pantallas de
  una sola tarea y ya tienen su propia barra con enlaces de vuelta. (El
  lienzo, que también vivía fuera de `(app)`, se borró en ADR-063.)
- Costo asumido: un contador de navegaciones en un módulo del bundle. Es
  estado global, con lo que eso implica —no se puede aislar por pestaña de
  React ni resetear entre pruebas sin exportar un `reiniciarHistorial()`—,
  pero es la única forma de saber algo que el framework no expone.
