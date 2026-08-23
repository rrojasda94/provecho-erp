# ADR-013 — Arquitectura frontend: Tailwind + shadcn/ui, shell estilo Odoo, gate por permiso

- Estado: aceptado
- Fecha: 2026-07-27 (actualizado 2026-07-27 y 2026-08-07 — ver notas abajo)

**Actualización 2026-08-07 — dirección visual revisada**: la sección 8 se
reescribe. La regla "superficies neutras, color con moderación" se mantiene y
se endurece; lo que cambia es que el color **sí** codifica algo: el área de
negocio, en cuatro tonos, y solo en filos e íconos. Cambian además la paleta
(contraste medido), la tipografía (Archivo en vez de Anton itálica para
títulos) y se agrega una regla de movimiento. Las decisiones estructurales
—Tailwind, shadcn/ui, shell estilo Odoo, gate por permiso, sin Radix, sin app
nativa— no se tocan. `docs/product/ui-ux.md` lleva el detalle.

**Actualización (misma fecha, sesión distinta)**: la sección 2 (primitivas de
interacción) cambió de Base UI directo a **shadcn/ui** — decisión revisada a
pedido del negocio para priorizar velocidad y facilidad de editar
color/forma por marca (ver razón completa en la sección 2). El resto del
ADR (Tailwind, shell estilo Odoo, gate por permiso, sin Radix, sin app
nativa) no cambia. `docs/product/frontend-architecture.md` (F2.4) y
`docs/prompts/frontend.md` se actualizan en el mismo cambio.

## Contexto

El frontend hoy son 2 pantallas (`/login`, `/dashboard`): Server Components +
Server Actions puros, JWT en cookie httpOnly, CSS vanilla con tokens de marca
en `frontend/app/globals.css`, sin librería de UI ni estado de cliente. Ese
patrón alcanzó para un dashboard de solo lectura, pero no hay ninguna
decisión de arquitectura técnica registrada (0 de 13 ADRs es de frontend) y
el backend ya expone 9 módulos de negocio (`users`, `inventory`, `sales`,
`purchases`, `production`, `accounting`, `rrhh`, más `marketing`/`gerencia`
sin API propia) detrás de RBAC granular (`GET /users/me` ya devuelve
`permisos: string[]` — lista plana de códigos, no solo roles).

Construir el PDV real (carrito, dialog de personalización, buscador con
ranking, upsell) sobre el patrón actual no alcanza: esas pantallas necesitan
estado de cliente de verdad, no solo Server Actions. Definir la arquitectura
ahora evita retrofit caro cuando entre PDV.

Requisitos del negocio para esta decisión (aportados directamente, no
derivados del código):

1. Pensado para **Android (tablet) y webapp** a la vez — no dos bases de
   código separadas.
2. **Tailwind CSS** para estilos.
3. **Base UI** (no Radix) como librería de primitivas de interacción.
4. La interfaz general debe **parecerse a Odoo**: home de apps + navegar
   dentro de cada módulo.
5. Los módulos deben **vivir dentro de la misma app** (no subdominios
   sueltos) y el usuario **solo ve los módulos para los que tiene permiso**.

## Decisión

### 1. Estilos: Tailwind CSS sobre los mismos tokens CSS ya definidos

Tailwind no reemplaza los tokens de marca de `globals.css` — los consume.
`tailwind.config.ts` mapea cada color/tipografía a la variable CSS existente
(`--color-primary`, `--color-dark`, etc.), nunca a un hex fijo:

```ts
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        primary: "var(--color-primary)",
        secondary: "var(--color-secondary)",
        dark: "var(--color-dark)",
        cream: "var(--color-cream)",
        accent: "var(--color-accent)",
        gray: "var(--color-gray)",
      },
      fontFamily: {
        heading: ["var(--font-heading)"],
        body: ["var(--font-body)"],
      },
    },
  },
};
```

Así `bg-primary` compila a `background-color: var(--color-primary)`: el
theming multi-marca de PDV/Kiosk (ADR pendiente en `ui-ux.md`) sigue
resolviéndose en runtime pisando las variables CSS en `<html data-theme>`
—Tailwind no necesita recompilar nada al cambiar de marca.

Con shadcn/ui (sección 2) el set de tokens se amplía a roles semánticos
(convención shadcn) mapeados a los MISMOS 6 tokens de marca — no se
inventa una paleta paralela, se remapea:

```css
/* globals.css — bloque por marca, ej. [data-brand="charlies"] */
/* Ojo: `--background` pasó a acero en el back office (2026-08-07); el crema
   quedó como superficie de PDV/Kiosk, que es donde este bloque por marca
   realmente se pisa. Ver sección 8 y docs/product/ui-ux.md. */
--background: var(--color-cream);
--foreground: var(--color-dark);
--primary: var(--color-primary);
--primary-foreground: #fff;
--secondary: var(--color-secondary);
--muted: var(--color-gray);
--accent: var(--color-accent);
--radius: 0.5rem; /* forma — un solo valor controla todos los componentes */
```

Esto es lo que responde directo al objetivo de negocio (perfiles de marca
editables rápido): un bloque de variables por marca (`[data-brand="..."]`)
controla color Y forma de cada componente shadcn a la vez, sin tocar
componentes.

**Regla dura que reemplaza a la de `docs/prompts/frontend.md`**: ningún hex
ni tamaño mágico ni en CSS ni en className — todo vía `tailwind.config.ts`
apuntando a los tokens, o clases utilitarias existentes de la escala de
Tailwind.

### 2. Primitivas de interacción: shadcn/ui (sobre Base UI)

**Revisado 2026-07-27** (ver nota de actualización arriba). Decisión
original: Base UI directo, construyendo cada componente a mano. Se cambia a
**shadcn/ui** por el objetivo real del negocio — editar color y forma por
marca rápido, con el mínimo trabajo de mantenimiento — al que shadcn le pega
mejor que construir a mano:

- **shadcn/ui no es una dependencia instalada, es un generador**: el CLI
  copia el código fuente de cada componente a `components/ui/` — queda en
  el repo, se edita directo, no hay versión de librería que actualizar ni
  API de terceros que aprender. Sigue siendo "nuestro" código, no un kit
  cerrado.
- **[Base UI](https://base-ui.com) sigue siendo la base** — shadcn/ui corre
  sobre Base UI (no Radix; el equipo de MUI mantiene ambos), así que la
  decisión "sin Radix" del negocio no cambia, solo cómo se llega a Base UI:
  a mano vs. vía shadcn.
- **Token set semántico ya cableado**: shadcn viene con roles
  (`--primary`, `--secondary`, `--background`, `--foreground`, `--muted`,
  `--accent`, `--destructive`, `--radius`) en vez de los 6 tokens crudos
  actuales — cambiar de marca es reemplazar un bloque de variables, los
  componentes leen el rol, no el color literal. `--radius` en particular
  controla la forma (esquinas) de **todos** los componentes con una sola
  variable — exactamente lo que se pidió ("más sencillo editar los colores
  y formas en el futuro").
- **Se ahorra construir el catálogo base a mano**: el plan original exigía
  levantar Button/Input/Select/Dialog/Tabs/Toast/etc. sobre Base UI uno por
  uno para llegar al mismo resultado de theming. shadcn ya los trae
  pre-armados sobre el mismo Base UI — se editan, no se construyen desde
  cero.

Se usa igual que se planeaba usar Base UI: solo donde hace falta
comportamiento accesible real (dialog, combobox, popover, tooltip,
tabs/menu) más el catálogo base (Button, Input, Select, Checkbox, Switch,
Card, Badge, Skeleton). Tarjetas/grillas simples sin comportamiento
interactivo siguen siendo HTML + Tailwind sin componente.

**Con qué cuidado**: el catálogo que trae `shadcn init` es más grande que lo
que este ERP necesita día uno — revisar y podar, no copiar todo el
registro. Si se usa un `--preset` de un registro externo (ej. tweakcn), es
punto de partida de **forma/espaciado únicamente** — los colores finales
siempre son los de `docs/product/ui-ux.md`, nunca los del preset tal cual.

**Alternativas evaluadas y descartadas para este mismo objetivo** (además
de las de la sección "Alternativas descartadas" original): Panda CSS /
vanilla-extract — no aportan nada extra para theming en runtime (las
variables CSS ya resuelven el cambio de marca en runtime, sin importar el
motor de estilos) y suman una herramienta de build sin beneficio real.

### 3. Shell general — home de apps + navegación dentro de módulo (patrón Odoo)

Dos niveles, replicando la estructura de Odoo:

**a) Home de apps** (`/` tras login): grilla de íconos, uno por módulo de
negocio (Ventas/PDV, KDS, Inventario, Compras, Producción, Contabilidad,
RRHH, Gerencia, Marketing...), cada uno con su color de marca. Odoo resuelve
esto con `ir.ui.menu` + `groups_id`: cada entrada de menú se oculta si el
usuario no pertenece al grupo requerido — ni siquiera se renderiza, no es un
disabled visual ([ver documentación/foros de Odoo sobre `ir.ui.menu` y
`web_icon`](https://www.odoo.com/forum/help-1/change-position-of-apps-in-switcher-121389)).
Acá se replica igual pero contra RBAC propio: `GET /users/me` **ya
devuelve** `permisos: string[]` (`src/modules/users/api/routers.py:102`) —
no hace falta tocar el backend. El home de apps es Server Component: lee
`permisos` una vez en el layout raíz (tras login) y filtra un registro
estático módulo → prefijo de permiso:

El registro se implementó como `frontend/lib/modulos.ts` (no
`apps.config.ts`), y desde 2026-08-07 cada entrada declara además su **área**
—de donde sale el color, ver sección 8— y un ícono de `lucide-react`:

```ts
// frontend/lib/modulos.ts
export const MODULOS: Modulo[] = [
  { clave: "compras", nombre: "Compras", prefijoPermiso: "purchases.",
    href: "/compras/ordenes-compra", area: "abastecimiento", Icono: ClipboardList,
    descripcion: "Proveedores y órdenes de compra" },
  // Cuando ver el módulo ya es un privilegio, `permiso` exacto manda sobre
  // el prefijo (catálogo: `sales.gestionar_catalogo`).
];

export function puedeVerModulo(permisos: string[], m: Modulo) { /* lib/permisos.ts */ }
```

El home agrupa por área en vez de listar doce fichas planas: un cajero ve dos
áreas y entiende cuál es su parte; un gerente ve las cuatro en el orden en que
transcurre el día.

**b) Dentro de un módulo**: sidebar vertical con el submenú del módulo activo
(Odoo migró de barra horizontal a sidebar vertical desde la v17) +
breadcrumb arriba. El breadcrumb **no** es el árbol de menú — ya está
especificado en `docs/product/ui-ux.md` como ruta de navegación del usuario
("patrón Odoo": cada pantalla visitada agrega un eslabón, no se resetea por
jerarquía); este ADR no cambia esa spec de producto, solo fija que se
implementa como estado de cliente simple (pila de `{label, href}`), sin
Base UI de por medio.

Cada ruta de módulo repite el mismo check de permiso que ya hace el home
(`layout.tsx` de `app/(app)/[modulo]/` redirige/403 si `permisos` no cubre
el prefijo) — el filtro del home es UX, no el único gate; sin esto alguien
con el link directo entraría a un módulo sin permiso aunque no lo vea en el
grid.

**Enmienda 2026-08-03 — el prefijo no alcanza para todos los módulos.**
Filtrar solo por prefijo asume que trabajar en un área equivale a poder
administrarla, y no es cierto: un cajero tiene `sales.crear`, `sales.cobrar`
y `sales.leer`, así que con el filtro por prefijo veía el módulo Catálogo y
entraba a la lista de productos comerciales —los leía completos, y recién
al guardar chocaba con el 403 de la API—. Que el backend lo rechace es
necesario pero no suficiente: lo que no le corresponde administrar no
debería aparecerle.

Por eso una entrada de `lib/modulos.ts` puede declarar `permiso` (código
exacto) además de `prefijoPermiso`, y el exacto manda cuando está presente:

```ts
{ clave: "catalogo", prefijoPermiso: "sales.", permiso: "sales.gestionar_catalogo", ... }
```

`puedeVerModulo()` (en `lib/permisos.ts`) es el único punto que resuelve
cuál de los dos aplica, y lo usan tanto el grid del home como el guard de
`ModuloShell` — un módulo no puede quedar visible en uno y bloqueado en el
otro. El permiso elegido es **el mismo que la API exige para escribir**, no
uno inventado para la pantalla: si mañana Catálogo pasa de Operaciones a
Comercial, se reasigna ese permiso a otro rol y no se toca código.

### 4. Convención de carpetas por módulo

```
frontend/app/
  (auth)/login/
  (app)/
    layout.tsx          # lee /users/me una vez, guarda sesión+permisos en contexto
    page.tsx            # home de apps (grilla filtrada)
    apps.config.ts
    sales/
      layout.tsx         # guard de permiso + sidebar del módulo
      page.tsx
      [venta]/page.tsx
    inventory/
      layout.tsx
      page.tsx
    ...
frontend/components/
  ui/                    # componentes shadcn/ui (copiados por el CLI, editables) sobre Base UI
  shell/                 # AppGrid, Sidebar, Breadcrumb — layout, no de un módulo
frontend/lib/
```

Refleja la modularidad que el backend ya tiene por Clean Architecture
(ADR-001) — un módulo de frontend no importa componentes internos de otro,
solo lo compartido en `components/`.

### 5. Estado de cliente

Sigue sin librería de estado global (Zustand/Redux) — YAGNI mientras no
aparezca un caso real que lo justifique (candidato futuro: carrito de PDV
compartido entre el listado de productos y el dialog de cobro, si crece
mucho). `useState`/`useReducer` de React alcanza para dialogs, carrito,
buscador con debounce. Server Components para todo lo de solo lectura
(dashboard, listados de back-office); Client Components (`"use client"`)
solo donde hay interacción real (PDV, Kiosk, KDS).

### 6. Testing

Cero tests de frontend hoy, mientras el backend tiene 317
(`tests/test_*.py`) y CLAUDE.md exige pruebas en cada cambio. Se adopta
**Playwright** para e2e de los flujos críticos (login, filtrado del home de
apps por permiso, crear venta, cobrar) antes de construir PDV — prioriza los
flujos de plata sobre cobertura unitaria de componentes sueltos.

### 7. Android: webapp responsive, no nativo

Esta pila (Next.js + Tailwind + shadcn/ui) es 100% web. Elegirla **resuelve**
el pendiente abierto en ROADMAP ("App Android (15+) — evaluar PWA vs
nativo"): queda decidido **PWA/responsive**, no una app nativa separada —
construir una app React Native/Kotlin en paralelo duplicaría toda esta
decisión sin necesidad. La tablet Android táctil obligatoria en PDV/Kiosk/
KDS/Inventario (`docs/product/ui-ux.md`) se cubre con diseño responsive +
touch targets, no con una segunda base de código.

### 8. Dirección visual: moderno y funcional, color con moderación

*(Reescrita el 2026-08-07. La versión original está en el historial de git;
lo que sigue reemplaza el párrafo anterior.)*

Ajuste pedido tras la primera propuesta: nada de un color de marca distinto
por tarjeta/módulo (el mockup inicial pintaba cada ícono del home de un
color de la paleta — leía recargado). **Esa regla sigue en pie**: doce
colores para doce módulos es un arcoíris. Lo que cambió es el nivel al que se
aplica el color.

**El color codifica el área de negocio, no el módulo.** Cuatro tonos
—Operación, Comercial, Abastecimiento, Administración— y cada uno aparece en
tres lugares y en ninguno más: el filo de 2–3 px del ítem activo del sidebar,
la ficha del ícono, y el borde de la tarjeta al apuntarla. Nunca como relleno
de una superficie grande. La diferencia con lo que se rechazó es que ahora el
color **significa** algo que el usuario necesita —en qué estación está
trabajando— en vez de ser variedad por variedad. Doce módulos en una lista
plana no se recuerdan; cuatro áreas sí, y coinciden con cómo el grupo divide
el trabajo y con cómo está escrita la documentación (`docs/compras/`,
`docs/rrhh/`…).

Superficies: acero (`#F2F4F7`) para el back office, blanco para las tarjetas,
crema **solo** en PDV/KDS/login. El crema de pared a pared bajaba el
contraste de las tarjetas blancas justo donde están los números.

Tipografía: **Archivo** (variable en peso y ancho) para títulos y cuerpo,
IBM Plex Mono para cifras, Anton **solo** para el logotipo. Anton en itálica
y versales para todos los títulos era la voz de la carta aplicada a pantallas
de trabajo, y es el ajuste menos escaneable que existe.

Movimiento (regla nueva): una sola curva, `180ms cubic-bezier(.2,.7,.2,1)`,
para entrada de pantalla, escalonado de grilla, filos de área y estados
(hover/foco/press). Sin parallax ni animación por scroll; nada que retrase
una acción. `prefers-reduced-motion: reduce` apaga todo.

El detalle —hex, contrastes medidos, tabla de áreas— vive en
`docs/product/ui-ux.md`, que es donde el negocio lo edita.

## Consecuencias

- `docs/prompts/frontend.md` se actualiza con estas reglas técnicas (hoy
  solo tenía branding/accesibilidad) en el mismo cambio que este ADR.
- ROADMAP: "App Android (15+)" pasa de "evaluar PWA vs nativo" a "PWA
  decidida por ADR-013" — sigue ⬜ (no construida), pero la pregunta ya no
  está abierta.
- Cada módulo nuevo de frontend agrega una fila a `MODULOS` en
  `frontend/lib/modulos.ts` —con su **área**, que es lo que le da color— y un
  `layout.tsx` propio con su guard de permiso. No hay paso manual adicional en
  el backend: `permisos` ya viaja en `/users/me`.
- Nuevas dependencias: `tailwindcss`, componentes de shadcn/ui (código
  copiado a `components/ui/`, no una librería instalada — trae consigo
  `@base-ui-components/react`, `class-variance-authority`, `tailwind-merge`
  como dependencias reales), `@playwright/test` (dev). Ninguna toca el
  backend.
- `npx shadcn@latest init` genera `components.json` (config del CLI) y
  escribe sobre `tailwind.config.ts`/`globals.css` — al correrlo, remapear
  sus tokens genéricos a los 6 tokens de marca de Provecho (ver ejemplo de
  la sección 1) antes de aceptar el resultado por defecto.
- El mecanismo de theming multi-marca de PDV/Kiosk (variables CSS en
  `data-theme`) queda fijado como parte de este ADR aunque el catálogo
  exacto de temas por marca sigue pendiente de negocio (ya declarado en
  `ui-ux.md`).

## Alternativas descartadas

- **Radix UI** — descartado explícitamente (pedido del negocio); Base UI
  cubre el mismo rol (headless, accesible, sin estilos) con el mismo modelo
  mental, así que no hay costo real de cambiarlo. shadcn/ui corre sobre Base
  UI, así que adoptarlo (sección 2) no reabre esta decisión.
- **Base UI directo, sin shadcn** (plan original de este ADR) — descartado
  tras revisar el objetivo real: construir el catálogo de componentes a
  mano llega al mismo mecanismo de theming (variables CSS) con más trabajo
  propio y un token set más pobre (6 tokens crudos vs. los roles semánticos
  + `--radius` que trae shadcn) — peor ajuste al pedido de negocio de poder
  editar color y forma por marca rápido. Ver sección 2 para el detalle
  completo de esta revisión.
- **MUI completo u otro kit con estética propia fuerte** — descartado: la
  interfaz debe parecerse a Odoo con la identidad Provecho, no a la
  estética por defecto de un kit; shadcn no cuenta como este caso porque no
  es un kit cerrado (el código se copia y se edita, no se hereda un tema
  ajeno que sobrescribir).
- **CSS vanilla sin Tailwind** (seguir como hoy) — descartado: con 9 módulos
  de negocio por construir, la velocidad de utilidades de Tailwind sobre los
  mismos tokens vale más que el costo de la dependencia; no se pierde nada
  del sistema de tokens actual, se lo consume distinto.
- **App nativa (React Native/Kotlin) para Android** — descartada por ahora:
  el requisito es táctil en tablet, no acceso a hardware nativo (cámara,
  NFC, notificaciones push) que justifique una segunda base de código;
  responsive + PWA cubre el caso de uso real declarado.
- **Permisos resueltos solo en el cliente** (ocultar módulo en el grid y
  confiar en eso) — descartado: el filtro del home es solo UX: cada
  `layout.tsx` de módulo repite el check de permiso server-side, igual que
  el backend ya hace deny-por-defecto en cada endpoint (`require_permission`
  en `src/modules/users/api/deps.py`). Ocultar sin verificar en el servidor
  sería seguridad por oscuridad.
