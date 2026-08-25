# UI / UX y branding

## Dos voces, no una (revisión 2026-08-07)

El brandboard de julio se aplicó por igual a todo: fondo crema de pared a
pared y cada `h1`–`h4` en Anton itálica y VERSALES. Es la voz correcta cuando
la marca le habla al cliente —PDV, kiosco, carta— y la peor posible en una
pantalla de trabajo: la itálica en versales es el ajuste menos escaneable que
existe, y sobre crema las tarjetas blancas pierden contraste justo donde
están los números.

Desde el rediseño hay **dos superficies con reglas distintas**:

| | Back office | PDV / KDS / login |
|---|---|---|
| Quién mira | personal, turnos de 8 h, tablas densas | cliente y quien atiende |
| Fondo | acero `#F2F4F7` | crema `#FFF4E6` |
| Titulares | Archivo condensada, caja normal | la voz de la marca |
| Logotipo | Anton, solo el wordmark | Anton |
| Color | tinta y gris; brasa solo en acciones | marca completa |

No es un tema nuevo ni un segundo set de tokens: es el **mismo** sistema,
donde el back office usa el subconjunto sobrio. El mecanismo de skins por
marca (abajo) no cambia.

## Branding Provecho (brandboard 2026-07, valores revisados 2026-08-07)

### Paleta

| Token CSS | Hex | Uso |
|-----------|-----|-----|
| `--color-primary` | `#C6390F` | Brasa — acciones primarias, logo |
| `--color-secondary` | `#7A1414` | Rescoldo — destructivo, crítico, error |
| `--color-dark` | `#15171C` | Tinta — texto y fondos oscuros |
| `--color-cream` | `#FFF4E6` | Crema — superficie de marca (PDV, KDS, login) |
| `--color-accent` | `#17864B` | Verde operación — estado "activo / conforme" |
| `--color-gray` | `#5F6B7A` | Humo — texto secundario |
| `--color-steel` | `#F2F4F7` | Acero — fondo del back office |

Los hex se movieron por contraste medido, no por gusto:

- El naranja `#F4511E` daba **3.4:1** sobre blanco y `text-primary` aparece 41
  veces en enlaces y títulos — no llegaba a AA. `#C6390F` da 5.3:1.
- El lima `#AEEA00` era, en la práctica, el color de 30 insignias de estado
  (`bg-accent/30` = emitida, recibida, cuadra, operativo, activa). En texto
  era ilegible y en insignia quedaba amarillento. El verde dice lo mismo y se
  lee.
- Tinta y humo pasaron de neutro cálido a neutro frío: es lo que hace que el
  fondo lea como acero de cocina y no como cartón.

### Un acento, no una paleta por área (revisión 2026-08-12, ADR-037)

Se probó un color por **área de negocio** (`--area-operacion`,
`--area-comercial`, `--area-abastecimiento`, `--area-administracion`) y se
descartó: ADR-013 §8 ya había rechazado el color por módulo o por tarjeta
—"la identidad de marca queda en tipografía y un acento consistente, no en
variedad de color de fondo"— y cuatro tintes son el mismo arcoíris con menos
pasos. La ficha del home con el ícono coloreado era, literalmente, el mockup
que ese ADR rechazó.

Queda **un acento** (`--hue`, que cuelga de `--marca-primary`), y aparece en
reposo solo donde marca **estado**: el ítem activo del sidebar y el filo del
rótulo de área. Todo lo demás arranca neutro y se enciende al apuntarlo.

Las **áreas de negocio siguen existiendo** como agrupación del home
(`AREAS` en `frontend/lib/modulos.ts`): Operación, Comercial,
Abastecimiento, Administración. Ordenan la grilla en el orden en que
transcurre el día. Ordenar no necesita pintar.

`--hue` existe como indirección —y no se usa `--primary` directo— para que el
PDV pueda recolorearlo por marca sin reescribir las cinco reglas que lo leen.

### Tipografías

- **Archivo** (variable, ejes de peso y **ancho**) — títulos y cuerpo. Una
  sola familia: el contraste entre un título y un párrafo lo dan el ancho
  condensado (`font-stretch: 92%`) y el peso, no una segunda grotesca que se
  le parece. En un ERP en español, donde las etiquetas son largas ("Órdenes
  de compra pendientes de aprobación"), condensar es además lo que hace que
  quepan sin abreviar.
- **IBM Plex Mono** — cifras: importes, cantidades, códigos internos, IDs.
  Clase `.cifra`. Una columna de dinero solo se compara si los dígitos ocupan
  el mismo ancho; el `body` lleva `font-variant-numeric: tabular-nums` por
  defecto.
- **Anton** — **solo el logotipo** (clase `.logotipo`) y las superficies de
  marca. Era la fuente de todos los títulos del ERP; ahora firma donde
  corresponde y no se mete en la lectura.
- Inter salió: era la tercera grotesca neutra y no aportaba nada que Archivo
  no hiciera.

### Identidad

- Logotipo: "P" en llamas + PROVECHO (Anton). Variantes: horizontal,
  vertical (tagline "Hub Gastronómico"), isotipo reducido, monocromática,
  verde lima sobre oscuro.
- En el back office el logotipo se reduce a wordmark + un cuadro de 8 px en
  brasa (que gira 45° al apuntarlo). Es la única firma cromática de la barra.
- Frase de campaña: **"¿Qué se te antoja hoy?"**
- Estilo gráfico: texturas urbanas (concreto, grunge, spray) — en las
  superficies de marca, no en las pantallas de trabajo.

### Movimiento

Una sola curva para todo el ERP, `--transicion: 180ms cubic-bezier(.2,.7,.2,1)`:
entra rápido y frena suave, como un cajón bien montado. Cuatro usos y no más:

1. **Entrada de pantalla** — 8 px de subida y opacidad, 220 ms, una vez por
   navegación (`components/shell/revelar.tsx`).
2. **Escalonado de grilla** — 25 ms entre fichas, hasta la sexta; más allá se
   percibe como lentitud (`.revelar-lista`).
3. **Filo del acento** — crece de arriba abajo al apuntar una ficha o al
   marcar el ítem activo del sidebar.
4. **Estados** — fondo, borde y sombra en hover/foco; 1 px de hundimiento al
   presionar.
5. **Diálogo** — `::backdrop` con desenfoque de 3 px y panel que entra con
   escala (200 ms). Solo la entrada: animar la salida de un `<dialog>` nativo
   exige `@starting-style` y `transition-behavior: allow-discrete` para no
   dejarlo colgado, y no compensa.
6. **Esqueletos** — `animate-pulse` mientras el servidor resuelve la
   pantalla (un `loading.tsx` por módulo).

Sin parallax, sin animación por scroll, sin nada que retrase una acción. Y
`prefers-reduced-motion: reduce` apaga todo: para parte del personal el
desplazamiento en pantalla produce mareo, no es una cortesía.

## Sistema de skins y temas (multi-marca)

- **Provecho** (branding de esta sección) es el tema por defecto de TODO el
  ERP. **Decidido (2026-07-27): Grupo Majambo no tiene tema propio** — no
  hay un branding corporativo distinto para back-office; Provecho es el
  único tema fuera de PDV/Kiosk. Si el grupo alguna vez lo necesita, es un
  tema nuevo a definir en ese momento, no una variante de Majambo que ya
  exista.
- **PDV y Kiosk son las pantallas con MÁS variación de skin**: son el "front"
  de cada marca del grupo (Charlie's, Ariana, La Avenida, ...) y cada una
  puede sobreescribir su propio tema completo (paleta, tipografía, logo),
  configurable por marca/sucursal en el módulo de ajustes.
- El resto de módulos (inventario, KDS, compras, contabilidad, comercial,
  RRHH, gerencia, marketing) usan **siempre** el tema de Provecho —
  **nunca** el tema de una marca de PDV.
- Mecanismo técnico: capa de resolución de tema (marca/sucursal activa →
  set de tokens CSS) separada del componente — nunca hex hardcodeado.

## Accesibilidad

- **Daltonismo / baja discriminación de color**: paleta(s) alternativa(s) y,
  en general, ningún estado (ej. badges de venta/stock) debe depender solo
  del color — reforzar con ícono/patrón.
- **Tamaño de fuente ajustable** por el usuario (escala de varios niveles)
  para reducir fatiga visual en personas con visión borrosa.
- Ambas preferencias se guardan en el **perfil del usuario** (no en el
  dispositivo/navegador), para que viajen con la persona entre equipos.
- La capa de accesibilidad (paleta/tamaño) es independiente de la capa de
  tema por marca — deben poder combinarse sin conflicto (ej. tema Charlie's
  + modo daltonismo + fuente grande, a la vez).

### Catálogo de paletas y tamaños de fuente (propuesta 2026-07-27, ✅ implementado 2026-08-12)

Resuelve el pendiente de catálogo exacto. Es una propuesta de partida —
válida para empezar a construir; se ajusta si una validación real con
usuarios daltónicos o de baja visión pide un cambio puntual, sin que eso
rehaga el mecanismo.

**Paletas — dos, no una por tipo de daltonismo.** Especializar una paleta
por cada tipo (protanopía, deuteranopía, tritanopía...) multiplica el
costo de mantener el sistema de diseño para un beneficio marginal, ya que
la regla ya vigente arriba (ícono/patrón, nunca solo color) cubre la mayor
parte del riesgo. En su lugar, un único modo alternativo que cubre
protanopía + deuteranopía (~95% de los casos de daltonismo, el par
rojo-verde) y sube el contraste general:

| Token semántico | Provecho (estándar) | Alto contraste / daltonismo |
|---|---|---|
| `--status-success` | `--color-accent` `#17864B` (verde operación) | `#0072B2` (azul) |
| `--status-danger` | `--color-secondary` `#7A1414` (rescoldo) | `#D55E00` (naranja vermellón) |
| `--status-warning` *(nuevo, no existe hoy)* | `#FFB300` (ámbar) | `#E69F00` (ocre) |
| `--status-info` *(nuevo, no existe hoy)* | `#1976D2` (azul) | `#56B4E9` (celeste) |

Paleta alternativa inspirada en Okabe-Ito (paleta categórica validada para
visión de color deficiente). `--color-primary`/`--color-secondary`
(marca, botones) no cambian entre modos — el riesgo de accesibilidad está
en los **estados semánticos** (badges de stock/venta), no en la identidad
de marca. Objetivo de contraste: WCAG AA (4.5:1 texto normal, 3:1 texto
grande/UI) como mínimo en ambos modos; AAA donde no cueste layout extra.

**Tamaño de fuente — 4 niveles**, como multiplicador (`--font-scale`) sobre
el tamaño base (`1rem` = 16px), aplicado en la raíz para que todo lo
dimensionado en `rem` escale junto:

| Nivel | `--font-scale` | Base efectiva |
|---|---|---|
| Estándar | `1.0` | 16px |
| Grande | `1.15` | ~18.4px |
| Muy grande | `1.3` | ~20.8px |
| Máximo | `1.5` | 24px |

Ambas preferencias viven en `usuario`
(`preferencia_paleta: estandar|alto_contraste`,
`preferencia_tamano_fuente: estandar|grande|muy_grande|maximo`), junto con
`preferencia_tema: claro|oscuro`. Se leen en `GET /users/me` y se cambian con
`PATCH /users/me/preferencias`, que **no exige permiso**: no hay privilegio
que otorgar en elegir el tamaño de la propia letra, y pedir uno dejaría la
accesibilidad fuera del alcance de quien más la necesita.

**Se resuelven en el servidor** (ADR-037): el layout raíz escribe
`class="dark"`, `data-escala` y `data-paleta` en `<html>`. No se usa
`next-themes` —aunque esté instalado para `sonner`— porque guarda en
`localStorage` y necesita un script inline antes del primer pintado, y la CSP
de `middleware.ts` firma cada script con un nonce por request. Por lo mismo
el tema no ofrece "seguir al sistema": detectarlo exige leer
`prefers-color-scheme` en el navegador.

Los dos ejes se combinan, como pide la sección anterior. El bloque
`[data-paleta="alto-contraste"]` se declara **después** de `.dark` —misma
especificidad, gana el último— y existe un
`.dark[data-paleta="alto-contraste"]` con la paleta Okabe-Ito aclarada: sus
valores están medidos contra blanco y sobre el fondo oscuro (`#101216`) el
azul cae a 3.6:1. Conserva el tono, que es lo que distingue los estados, y
sube la luminosidad, que es lo que los hace legibles.

| Token | Estándar | Alto contraste | Oscuro | Oscuro + alto contraste |
|---|---|---|---|---|
| `--status-success` | `#17864B` | `#0072B2` | `#2EA86A` | `#3D9EE0` |
| `--status-danger` | `#7A1414` | `#D55E00` | `#E5484D` | `#EF7D1A` |
| `--status-warning` | `#FFB300` | `#E69F00` | `#FFB300` | `#F0B429` |
| `--status-info` | `#1976D2` | `#56B4E9` | `#4D94FF` | `#56B4E9` |

La regla de "ningún estado depende solo del color" no queda como convención:
el ícono viaja **atado al tono** en `components/estado/insignia.tsx`. Si
fuera una prop opcional, la pantalla número treinta y uno lo olvidaría y
nadie lo notaría en la revisión.

### Modo oscuro (nuevo 2026-08-12, ADR-037)

El brandboard nunca contempló pantallas oscuras fuera del PDV y el KDS (y,
hasta que se borró en ADR-063, el lienzo). Se agrega para el resto del ERP:
la oficina a las 3 p.m. y la cocina a las 6 a.m. no son la misma luz, y el
turno de cierre trabaja de noche.

Remapea **roles**, nunca los `--marca-*`. Dos colores se recalculan por
contraste medido: `--primary` vuelve al naranja original `#F4511E` (la brasa
`#C6390F` cae a 3.6:1 sobre fondo oscuro; el naranja de origen sube a 5.4:1)
y `--secondary` pasa de rescoldo a `#E5484D`.

## Responsive y plataformas

- Todo el ERP es responsive: webapp de escritorio + tablet Android (táctil).
- **Uso táctil en tablet Android obligatorio**: PDV, Kiosk, KDS e Inventario
  (conteo/ajuste se opera desde tablet en almacén/sucursal).
- **Resto de módulos** (compras, contabilidad, comercial, RRHH, gerencia,
  marketing): orientados a PC/escritorio; deben seguir siendo responsive
  (no romperse en pantallas chicas) pero sin exigir optimización táctil
  dedicada.
- Los módulos táctiles deben funcionar tanto con mouse/teclado (PC) como con
  touch (tablet): sin interacciones hover-only, touch targets de tamaño
  adecuado.

### Qué significa "no romperse en pantallas chicas"

Dos reglas, y las dos se verifican solas en `frontend/uso/responsive.spec.ts`
sobre tres medidas (teléfono 390×844, tablet vertical 820×1180, PC 1440×900):

1. **Ninguna opción desaparece al angostar la pantalla.** Un control puede
   cambiar de lugar, entrar en un panel que se alterna o quedar detrás de un
   scroll; lo que no puede es dejar de existir ni quedar dibujado fuera de un
   contenedor que lo recorta. `display: none` por ancho es la forma más fácil
   de romper esto: fue lo que escondió el ticket entero del PDV —pedido,
   totales, «Enviar» y «Cobrar»— en toda tablet en vertical.
2. **Todo diálogo modal queda centrado en la pantalla**, en cualquier ancho.
   El centrado lo da el navegador (`margin: auto` sobre los `inset: 0` del
   `<dialog>` modal) y es más frágil de lo que parece: el preflight de
   Tailwind lo pisa con `margin: 0`, y cualquier ancestro con un `transform`
   distinto de `none` —incluida una animación con `animation-fill-mode: both`
   cuyo último fotograma es `transform: none`, que computa a la matriz
   identidad— se vuelve bloque contenedor del diálogo y lo clava en su esquina
   superior izquierda. Por eso las animaciones de entrada del ERP usan
   `backwards` y no `both`.

En el PDV y el KDS, además, el ancho de mostrador (≥ 60rem) muestra los dos
paneles a la vez; por debajo se alternan con un botón que solo existe en ese
ancho. Alternar es aceptable, esconder no.

## Flujos clave de UI

### PDV — selección de producto → dialog de personalización

- Al seleccionar un producto comercial en el PDV (y en Kiosk), se abre un
  **dialog de personalización** con los modificadores admitidos por ese
  producto (tamaño, combinación, extras, restas — entidad `modificador`,
  `docs/architecture/data-model.md` §Operación comercial).
- El dialog es la única forma de configurar el producto antes de agregarlo
  al carrito; el resultado es una `variante_producto` (modificadores
  aplicados + receta/precio resultante).
- El orden de aplicación de los modificadores es siempre
  tamaño → combinación → extras → restas (RN-PRD-004), sin importar el
  orden en que el cajero/cliente los toca en el dialog.
- RN-PRD-005: todo modificador admitido por el producto debe reflejarse en
  el PDV de la sucursal — el dialog no puede ofrecer configuraciones que el
  producto no admite, ni ocultar las que sí admite.
- Pendiente definir con el negocio: diseño visual del dialog, si combos se
  configuran en el mismo dialog o en uno propio (`combo_item`), y el
  comportamiento en Kiosk (autoservicio, sin cajero) vs. PDV asistido.

### KDS — tarjeta de pedido, tachar ítem por ítem (implementado 2026-08-03)

Referencia explícita: la *preparation display* de Odoo (se revisó su
documentación antes de diseñar esta pantalla). Se replica lo que resuelve
el problema y se descarta lo que choca con las reglas ya decididas.

- **Una tarjeta por pedido**, en grilla; encabezado con `#numero_orden`,
  `referencia_atencion` ("Mesa 5", "Rappi #1042"), modalidad/canal y el
  estado agregado del pedido. El borde superior colorea ese estado
  (gris pendiente → ámbar en preparación → verde listo) para leerlo a
  distancia.
- **Un toque sobre el ítem lo tacha** (`line-through` + check + fondo
  verde): así lo hace Odoo y así se opera con las manos ocupadas. El toque
  lleva el ítem hasta `listo`, encadenando `en_preparacion` si venía en
  `pendiente` — la API solo acepta avanzar de a un estado.
- **Botón "Todo listo"** = el "click en la tarjeta" de Odoo: marca de una
  vez todos los ítems que faltan.
- **El ítem tachado se queda a la vista**, no desaparece: la tarjeta sale
  de la cola de esa estación recién cuando todos sus ítems están listos
  (igual que en Odoo, donde la tarjeta avanza de etapa al tacharse
  entera). Requirió corregir `cola_pantalla` en el backend.
- **El avance se ve en TODAS las pantallas de la sucursal** donde aparezca
  ese pedido, porque ninguna pantalla guarda estado propio: el avance vive
  en `venta_item.estado_preparacion` (RN-CUP-003) y cada pantalla es un
  filtro sobre él. Hoy la propagación es por **polling cada 3 s**; el push
  en vivo es deuda declarada (`ROADMAP.md`).
- **No se replica el "recall"** (deshacer/retroceder) de Odoo: RN-CUP-002
  prohíbe el retroceso de estado. Tocar un ítem ya tachado no lo devuelve,
  avisa que el avance no se deshace.
- **La entrega no se marca ítem por ítem**: en pantallas de tipo
  `despacho`, y solo con `sales.entregar_pedido` (RN-CUP-006), la tarjeta
  muestra "Entregar" cuando el pedido completo está listo.
- Pantalla completa fuera del shell (como el PDV), paleta oscura, objetivos
  táctiles ≥ 3 rem, sin interacciones hover-only. La estación elegida viaja
  en la URL (`/kds?pantalla=<id>`) para que cada tablet la deje en
  favoritos.
- **`/kds` sin estación = tablero de estaciones**: la misma lista sirve para
  elegir dónde queda la tablet y para **configurar las pantallas** (crear,
  editar, activar/desactivar, borrar; filtro por categorías) con
  `kds.configurar`, que desde 2026-08-24 es solo de administración (ADR-065).
  Van juntas a propósito — es la misma lista, y quien configura una estación
  lo hace mirando el tablero que la cocina usa. **Desactivar y borrar no son
  lo mismo**: desactivar la apaga y la deja volver; borrar la saca de la lista
  y libera su nombre, y se rechaza si todavía tiene cola. Quien solo opera ve
  la lista sin los botones y el texto le dice a quién pedirle una pantalla.

### Pad de asistencia — tarjeta con tu nombre y tu PIN (implementado 2026-08-24)

- Pantalla completa fuera del shell, misma paleta oscura del PDV y del KDS y
  por la misma razón: es una tablet colgada en un pasillo y se lee de paso.
- **Dos toques y nada más**: se toca la tarjeta con el nombre, se teclea el
  PIN en el mismo `<Pinpad>` del PDV (ADR-045/050, sin `<input>`), y el acuse
  ocupa la pantalla entera tres segundos antes de volver a la grilla. La cola
  del cambio de turno no puede esperar a que alguien confirme nada.
- **La tarjeta dice qué va a pasar** («marcar entrada» / «marcar salida»),
  pero no lo decide: eso sale del estado del día en el servidor. La tarjeta de
  quien ya cerró su jornada queda apagada y no se puede tocar.
- **Solo el nombre.** Ni cargo, ni documento, ni sueldo: la pantalla está a la
  vista de todo el que pase por la cocina.
- Un PIN errado borra lo tecleado entero en vez de dejarlo escrito — dejarlo
  invita a probar el siguiente dígito en vez de volver a empezar.

### Navegación — breadcrumbs por ruta de usuario, no por jerarquía

- El breadcrumb sigue la **ruta que recorrió el usuario**, no la jerarquía
  de dónde vive la funcionalidad (patrón Odoo): cada pantalla nueva a la
  que se entra desde la actual agrega un eslabón; no se resetea al estilo
  "Sección > Subsección > Pantalla".
- Ejemplo: si desde un producto se abre su receta y desde la receta se abre
  un insumo, el breadcrumb queda `Producto X > Receta > Insumo Y` — cada
  eslabón es clicable para volver exactamente al punto de origen de esa
  acción, sin perder el resto del recorrido intermedio.
- La **navegación jerárquica** (ir directo a un módulo/pantalla sin haber
  pasado por ahí) se hace por **menús desplegables**, no por el breadcrumb
  — son dos mecanismos distintos y no se mezclan.
- Pendiente definir con el negocio: límite de eslabones antes de colapsar
  (ej. "... > Y > Z") y qué pasa con el breadcrumb al cambiar de módulo
  desde el menú (¿se reinicia o se apila?).

### Formularios — ayuda contextual por campo

- Todo campo de formulario tiene **hover** (tooltip) que explica qué debe
  llenarse: el término de negocio si no es obvio, y/o el formato esperado
  (ej. `RUC: 11 dígitos`, `Fecha de vencimiento: no puede ser pasada`).
- Aplica a todos los módulos, no solo PDV — es una regla transversal de
  formularios.
- Pendiente definir con el negocio: contenido exacto de cada tooltip (se
  redacta por campo al construir cada formulario, no de una vez).

### Buscadores — contextuales, por nombre/insumo/exclusión, con ranking

- El buscador debe llevar directo al reporte/ítem/información buscada por
  **palabra clave contextual**, no solo por coincidencia exacta de nombre.
- Búsquedas admitidas (mínimo, en PDV/Kiosk/web): por **nombre de
  producto**, por **insumo/ingrediente** (cruce contra `receta_item` — un
  producto aparece si su receta lo usa), y por **exclusión** ("que no
  tenga XXXX" → productos cuya receta NO incluye ese insumo).
- Cuando no hay una coincidencia única y clara, se muestra una **lista de
  resultados posibles ordenada por probabilidad/relevancia** — no un único
  resultado forzado ni una lista sin orden.
- Aplica también a buscadores de otros módulos (reportes, ítems de
  inventario, etc.), no solo al de producto en el punto de venta.
- **Ranking por historial de uso** (decidido con el negocio, 2026-07-26):
  el orden por relevancia se basa en patrones de uso reales (qué
  encuentra/selecciona cada usuario, qué se busca/vende más), no solo en
  similitud de texto. El sistema debe poder detectar esos patrones para
  mejorar resultados con el tiempo — el objetivo explícito es reducir la
  fricción de búsqueda en versiones futuras a medida que aprende del uso.
- Nota técnica (no bloquea la spec): arrancar con full-text search con
  score de relevancia (ej. `pg_trgm`/`tsvector` de Postgres); el historial
  de uso se suma como señal de ranking encima de eso — no reemplaza la
  búsqueda estructurada por nombre/insumo/exclusión, la reordena.
- Pendiente definir con el negocio: qué otros campos son buscables por
  módulo, y el diseño concreto de la señal de historial (por usuario, por
  sucursal, global — y con qué ventana de tiempo).

### Carrito — dialog de venta sugerida (upsell) antes de continuar

- Al elegir un producto o grupo de productos y avanzar hacia el carrito,
  se abre un **dialog de productos sugeridos** que el usuario puede
  agregar rápido con un toque/clic (sin repetir el flujo completo de
  selección).
- Si el usuario no quiere agregar nada, puede **descartar el dialog** y
  seguir directo al carrito o a cobrar — nunca es un paso obligatorio.
- Aplica en PDV, Kiosk y web.
- **Criterio de sugerencia** (decidido con el negocio, 2026-07-26): dos
  fuentes, no excluyentes entre sí — (1) **complementos** del producto
  elegido (típicamente bebidas, pero también otros complementos definidos
  por producto) y (2) **producto en promoción vigente** (`promocion`),
  independiente de si complementa al elegido o no.
- Pendiente definir con el negocio: cómo se configura la relación
  producto → complemento sugerido (fija por producto vs. regla de venta
  cruzada más general), y si el dialog aparece siempre o solo bajo
  ciertas condiciones (ej. no repetir la sugerencia ya rechazada en el
  mismo pedido).

## Reglas de implementación

- Colores y fuentes SOLO vía tokens CSS (`frontend/app/globals.css`).
  Nunca hex hardcodeado en componentes.
- Branding Provecho en TODO el ERP; el **PDV/Kiosk** sobreescriben los
  tokens con el branding de cada marca (configurable en el módulo de
  ajustes) — ver "Sistema de skins y temas".
- Preferencias de accesibilidad (paleta y tamaño de fuente) se leen del
  perfil del usuario logueado, no del dispositivo.
- Responsive en todas las pantallas (webapp + Android 15+); táctil
  obligatorio en PDV/Kiosk/KDS/Inventario — ver "Responsive y plataformas".
- **Formato título automático en nombres** (ADR-023): todo campo que nombre
  una entidad (producto, receta, insumo, grupo de opciones) se normaliza al
  **salir del campo**, no mientras se escribe —corregir el texto bajo los
  dedos del usuario es peor que no corregirlo—. Regla del español:
  conectores en minúscula salvo al inicio ("Pizza de Peperoni Familiar"),
  siglas cortas en mayúscula respetadas ("Pizza XL"). El servidor aplica lo
  mismo (`shared/texto.py`): la pantalla es comodidad, la garantía está en
  la API.
- **Campos de cantidad que aceptan aritmética** (RN-COM-024): en recetas,
  el campo admite "1000/3" o "250*1.5" y muestra el resultado debajo
  mientras se escribe. Lo que se guarda lo calcula el **servidor** a partir
  de la expresión, redondeado a los decimales de la unidad de medida
  correspondiente (RN-GER-010); el navegador solo previsualiza. Una
  expresión a medio escribir ("250*") no es un error: no se muestra
  resultado y no se envía nada.

## Pendiente de definición (con el negocio)

- Menús, buscadores, atajos de teclado, dashboards y diseño visual de
  pantallas. **Mecanismo de navegación ya decidido** (ADR-013: home de apps
  + sidebar por módulo estilo Odoo) — pendiente es el contenido de cada
  menú, no la estructura.
