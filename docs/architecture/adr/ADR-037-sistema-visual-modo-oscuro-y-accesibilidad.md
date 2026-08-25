# ADR-037 — Sistema visual: dónde vive el dinamismo, modo oscuro y accesibilidad

- Estado: aceptado
- Fecha: 2026-08-12
- Complementa: ADR-013 (arquitectura frontend), ADR-035 (lienzo de nodos)

## Contexto

El encargo fue «actualizar el frontend a una versión más dinámica y moderna
que incluya todas las directrices y diseños planeados». Choca de frente con
una decisión ya tomada y escrita: **ADR-013 §8** dice que la identidad de
marca vive en la tipografía y en un acento consistente, «no en variedad de
color de fondo», y rechaza explícitamente el mockup que pintaba cada ícono
del home de un color distinto porque «leía recargado».

Los dos no son incompatibles, pero solo si se responde primero una pregunta:
**si el dinamismo no va en el color, ¿dónde va?**

El estado de partida hacía la pregunta urgente. Sobre el código verificado:

- `components/ui/` tenía 14 primitivas de shadcn y **solo 9 archivos las
  importaban**. El otro 90% de las pantallas eran Tailwind inline sobre
  `<table>`, `<dialog>` y `<button>` nativos.
- El buscador de `components/tabla/tabla-datos.tsx` era un `<input>` **sin
  una sola clase de estilo**, y el estado del orden un `" ↑"` concatenado al
  texto de la cabecera. Ese componente lo usan 28 pantallas.
- ADR-035 ya había registrado el síntoma en una frase del usuario: *«parece
  más HTML que elementos interactivos, se siente barato»*. Se resolvió para
  una pantalla (el lienzo) y no para el resto.
- `docs/product/ui-ux.md` tenía desde julio el catálogo de accesibilidad
  cerrado —con hex exactos, cuatro niveles de escala tipográfica y la regla
  de que ningún estado dependa solo del color— y **ni un token escrito**.
- Tailwind v4 no declara la variante `dark` por estrategia de clase. Las
  decenas de clases `dark:` que `shadcn add` ya había dejado en
  `components/ui/**` **no compilaban a nada**. No fallaban: simplemente no
  existían.

## Decisión

### 1. El dinamismo se gasta en seis ejes, y ninguno es el color

| Eje | Qué cambia |
|---|---|
| **Movimiento** | Entrada de pantalla, escalonado en grillas, `::backdrop` con desenfoque, diálogo que entra con escala. Todo por keyframes CSS. |
| **Profundidad** | Tres pasos de elevación (`--sombra-1..3`) teñidos con la tinta de marca, no con negro puro. |
| **Densidad y ritmo** | Un encabezado de pantalla y una tabla con la misma métrica en todos lados, en vez de cada pantalla inventando su espaciado. |
| **Jerarquía tipográfica** | Archivo variable en ancho, y `font-variant-numeric: tabular-nums` en toda cifra. En un ERP el contenido son números: que las columnas se alineen es lo que separa "software serio" de "página con tablas". |
| **Estados** | hover / active / focus-visible / disabled / cargando / vacío / error en cada control. |
| **Feedback** | Esqueletos por ruta, `aria-busy`, vacíos con ícono y acción, toasts. |

El color sigue disciplinado: superficies neutras, y `--hue` —un acento único—
reservado para acción primaria, ítem activo del sidebar y alertas.

**Se probó y se descartó un color por área de negocio** (`--area-operacion`,
`--area-comercial`, `--area-abastecimiento`, `--area-administracion`). Cuatro
tintes son el mismo arcoíris de ADR-013 §8 con menos pasos, y la ficha del
home con el ícono coloreado era literalmente lo que ese ADR rechazó. Las
áreas **sobreviven como agrupación** del home: ordenan, y ordenar no necesita
pintar.

### 2. Ninguna dependencia nueva de UI

- **Animación**: keyframes CSS + `tw-animate-css`, ya importado. Se evaluó
  `motion`. Se descartó: todo lo que hace falta (entrada, elevación al hover,
  escala del diálogo, escalonado) es CSS, Base UI expone
  `data-starting-style`/`data-ending-style` para animar hasta las salidas, y
  cada componente animado con `motion` se vuelve `"use client"` — contra la
  regla de Server Components por defecto. Se reconsidera si aparece una
  animación de layout compartido.
- **Paleta de comandos**: `@base-ui/react` Autocomplete + Dialog. Se descartó
  `cmdk`: trae su propio motor de coincidencia difusa para ~50 entradas
  estáticas y arrastra el árbol de Radix que ADR-013 descartó.
- **Tema**: no se usa `next-themes` (ver punto 4).

Sí se agregaron primitivas del registro `base-nova` (`tooltip`,
`breadcrumb`, `dropdown-menu`, `skeleton`), que es traer código al repo, no
una dependencia.

### 3. Modo oscuro en el back office

El brandboard nunca contempló pantallas oscuras fuera del PDV, el KDS y el
lienzo. Se agrega para el resto del ERP porque la oficina a las 3 p.m. y la
cocina a las 6 a.m. no son la misma luz, y el turno de cierre trabaja de
noche.

Remapea **roles**, nunca los `--marca-*`. Dos colores sí se recalculan, por
contraste medido:

- `--primary` vuelve al naranja original `#f4511e`. Sobre acero claro daba
  3.4:1 y por eso se oscureció a brasa (`#c6390f`, 5.3:1); sobre fondo oscuro
  la brasa cae a 3.6:1 y el naranja de origen sube a 5.4:1. Es el mismo
  criterio aplicado al fondo contrario.
- `--secondary` sube de rescoldo (`#7a1414`, invisible en oscuro) a `#e5484d`
  (4.8:1).

### 4. Las preferencias se resuelven en el servidor, no en el navegador

`docs/product/ui-ux.md` ya exigía que paleta y tamaño de letra vivieran **en
el perfil del usuario, no en el dispositivo**, «para que viajen con la persona
entre equipos». El motivo es operativo y verificable en el local: la misma
tablet la usan tres turnos, y la misma persona salta de la caja a la oficina.

Se extiende esa decisión al tema. Las tres viven en `usuario`
(`preferencia_paleta`, `preferencia_tamano_fuente`, `preferencia_tema`), el
layout raíz las lee y escribe `class="dark"`, `data-escala` y `data-paleta`
en `<html>`.

**Por qué no `next-themes`** (que ya estaba instalado, alimentando a
`sonner`): guarda en `localStorage` y necesita un script inline que corra
antes del primer pintado para evitar el parpadeo. La CSP de `middleware.ts`
firma cada script con un nonce por request, con `'strict-dynamic'`. Abrirle
una excepción al único control que de verdad frena XSS, para evitar un
parpadeo que resolviendo en servidor no existe, no es un intercambio que
convenga.

**Consecuencia aceptada**: no hay opción «seguir al sistema». Detectarla
exige leer `prefers-color-scheme` en el navegador, que es exactamente el
script que no se quiere. Con la preferencia guardada en el perfil, aporta
poco: se elige una vez y viaja a todas las máquinas.

**Segunda consecuencia**: cada cambio de preferencia es un viaje al servidor
más un `revalidatePath("/", "layout")`. Es más lento que un toggle local. Son
acciones que una persona hace una vez, no en cada pantalla.

### 5. Los dos ejes de accesibilidad se combinan

`[data-paleta="alto-contraste"]` se declara **después** del bloque `.dark`.
Los dos viven en `<html>` con la misma especificidad, así que gana el último:
declarado antes, el tema oscuro apagaba la paleta accesible y quien la había
activado veía los colores de siempre. Y existe un bloque
`.dark[data-paleta="alto-contraste"]` con la paleta Okabe-Ito **aclarada**:
sus valores están medidos contra blanco y sobre `#101216` el azul cae a
3.6:1. Conserva el tono —que es lo que distingue los estados— y sube la
luminosidad, que es lo que los hace legibles.

El ícono obligatorio por estado no queda como convención: viaja atado al tono
en `components/estado/insignia.tsx`. Si fuera una prop opcional, la pantalla
número treinta y uno lo olvidaría y nadie lo notaría en la revisión.

### 6. Se arregla primero lo que muchas pantallas heredan

`components/tabla/tabla-datos.tsx` (28 pantallas) y
`components/formulario/dialogo-formulario.tsx` (17) se rediseñan **con la
firma de props compatible hacia atrás**: ninguna pantalla llamadora se edita.
Las trece pantallas que todavía escriben su propio `<dialog>` heredan los
campos vestidos por descendencia desde la clase `.erp`, que marca la raíz del
back office y **no alcanza** al PDV, al KDS ni al lienzo.

Ese bloque de CSS va **fuera de todo `@layer`** a propósito: dentro de una
capa perdería siempre contra las utilidades de Tailwind que esas pantallas ya
escribieron (`rounded-lg`, `p-0`), sin importar la especificidad. Es un parche
con fecha de vencimiento — se borra cuando esas pantallas migren al molde.

## Consecuencias

- El brandboard de julio queda enmendado en `docs/product/ui-ux.md`: dos
  voces (back office sobrio sobre acero; marca completa en PDV, KDS y login),
  con los hex movidos por contraste medido.
- Los `--status-*` son ahora la única forma correcta de comunicar un estado.
  Las pantallas que siguen con `bg-accent/30` a mano quedan como deuda
  registrada.
- `@custom-variant dark` es obligatorio en `globals.css`. Sin esa línea las
  clases `dark:` de `components/ui/**` vuelven a ser código muerto, y el
  síntoma solo se ve en el navegador.
- El PDV y el KDS **no se tocan**. Tienen su propia paleta oscura scoped por
  clase raíz, están validados en uso y están en el camino del dinero.
  Migrarlos es su propia entrega. (El lienzo, que también estaba en esta
  lista, se borró en ADR-063.)
- Tres columnas nuevas en `usuario` y un endpoint sin permiso
  (`PATCH /users/me/preferencias`): no hay privilegio que otorgar en elegir el
  tamaño de la propia letra, y exigir uno dejaría la accesibilidad fuera del
  alcance de quien más la necesita.

## Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Un color por módulo o por área | ADR-013 §8 ya lo rechazó; cuatro tintes son el mismo problema con menos pasos |
| `motion` / `framer-motion` | Todo lo necesario es CSS; convierte cada componente animado en cliente |
| `cmdk` para la paleta | Motor de fuzzy search para 50 entradas estáticas, y arrastra Radix |
| `next-themes` para el tema | Exige un script inline que la CSP con nonce tendría que autorizar |
| Preferencias en `localStorage` | ui-ux.md pide perfil; en un local la tablet la comparten tres turnos |
| Reemplazar el `<dialog>` nativo por el `Dialog` de shadcn | Es una decisión documentada con motivo, y el despacho manual de la acción arregla un bug real de React 19 |
| Migrar las 28 pantallas de tabla una por una | La firma compatible hacia atrás logra lo mismo tocando cinco archivos |
