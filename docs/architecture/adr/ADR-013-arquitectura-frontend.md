# ADR-013 — Arquitectura frontend: Tailwind + Base UI, shell estilo Odoo, gate por permiso

- Estado: aceptado
- Fecha: 2026-07-27

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
—Tailwind no necesita recompilar nada al cambiar de marca. Mismo patrón que
usa shadcn/ui, no es una invención de este ADR.

**Regla dura que reemplaza a la de `docs/prompts/frontend.md`**: ningún hex
ni tamaño mágico ni en CSS ni en className — todo vía `tailwind.config.ts`
apuntando a los tokens, o clases utilitarias existentes de la escala de
Tailwind.

### 2. Primitivas de interacción: Base UI

[Base UI](https://base-ui.com) (`@base-ui-components/react`) — librería
headless mantenida por el equipo de MUI, sucesora directa del linaje que
incluye a Radix (mismo espacio: overlays/combobox/dialog accesibles, cero
estilos propios, se pinta 100% con Tailwind). Es la base de facto de
shadcn/ui hoy. Se usa **solo para lo que de verdad necesita comportamiento
accesible no trivial** — dialog (personalización de producto, upsell),
combobox (buscador), popover, tooltip (ayuda contextual por campo),
tabs/menu (navegación dentro de módulo). Todo lo demás (tarjetas, grillas,
botones simples) sigue siendo HTML + Tailwind sin librería, como hoy.

No se adopta un kit de componentes ya estilizado (shadcn/ui, MUI completo,
etc.) — el pedido es una identidad visual propia parecida a Odoo, no la
estética de un kit de terceros; adoptar uno completo obligaría a
sobre-escribir su tema entero, que es más trabajo que partir de primitivas
sin estilo.

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

```ts
// app/(app)/apps.config.ts
export const APPS = [
  { modulo: "sales", nombre: "Ventas / PDV", prefijo: "sales.", icono: PosIcon, color: "primary" },
  { modulo: "kds", nombre: "Cocina (KDS)", prefijo: "kds.", icono: KdsIcon, color: "accent" },
  { modulo: "inventory", nombre: "Inventario", prefijo: "inventory.", icono: BoxIcon, color: "dark" },
  { modulo: "purchases", nombre: "Compras", prefijo: "purchases.", icono: CartIcon, color: "secondary" },
  { modulo: "production", nombre: "Producción", prefijo: "production.", icono: ChefIcon, color: "accent" },
  { modulo: "accounting", nombre: "Contabilidad", prefijo: "accounting.", icono: LedgerIcon, color: "dark" },
  { modulo: "rrhh", nombre: "RRHH", prefijo: "rrhh.", icono: PeopleIcon, color: "primary" },
] as const;

export function appsVisibles(permisos: string[]) {
  return APPS.filter((a) => permisos.some((p) => p === "*" || p.startsWith(a.prefijo)));
}
```

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
  ui/                    # wrappers propios sobre Base UI (Dialog, Combobox, Tooltip...)
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

Esta pila (Next.js + Tailwind + Base UI) es 100% web. Elegirla **resuelve**
el pendiente abierto en ROADMAP ("App Android (15+) — evaluar PWA vs
nativo"): queda decidido **PWA/responsive**, no una app nativa separada —
construir una app React Native/Kotlin en paralelo duplicaría toda esta
decisión sin necesidad. La tablet Android táctil obligatoria en PDV/Kiosk/
KDS/Inventario (`docs/product/ui-ux.md`) se cubre con diseño responsive +
touch targets, no con una segunda base de código.

### 8. Dirección visual: moderno y funcional, color con moderación

Ajuste pedido tras la primera propuesta: nada de un color de marca distinto
por tarjeta/módulo (el mockup inicial pintaba cada ícono del home de un
color de la paleta — leía recargado). Superficies neutras (blanco/gris/crema)
por defecto; `--color-primary`/`--color-accent` se reservan para acción
primaria, ítem activo/seleccionado del sidebar y alertas. La identidad de
marca queda en tipografía (Anton Italic + Inter) y un acento consistente, no
en variedad de color de fondo.

## Consecuencias

- `docs/prompts/frontend.md` se actualiza con estas reglas técnicas (hoy
  solo tenía branding/accesibilidad) en el mismo cambio que este ADR.
- ROADMAP: "App Android (15+)" pasa de "evaluar PWA vs nativo" a "PWA
  decidida por ADR-013" — sigue ⬜ (no construida), pero la pregunta ya no
  está abierta.
- Cada módulo nuevo de frontend agrega una fila a `APPS` en
  `apps.config.ts` y un `layout.tsx` propio con su guard de permiso — no hay
  paso manual adicional en el backend, `permisos` ya viaja en `/users/me`.
- Nuevas dependencias: `tailwindcss`, `@base-ui-components/react`,
  `@playwright/test` (dev). Ninguna toca el backend.
- El mecanismo de theming multi-marca de PDV/Kiosk (variables CSS en
  `data-theme`) queda fijado como parte de este ADR aunque el catálogo
  exacto de temas por marca sigue pendiente de negocio (ya declarado en
  `ui-ux.md`).

## Alternativas descartadas

- **Radix UI** — descartado explícitamente (pedido del negocio); Base UI
  cubre el mismo rol (headless, accesible, sin estilos) con el mismo modelo
  mental, así que no hay costo real de cambiarlo.
- **shadcn/ui u otro kit ya estilizado** — descartado: la interfaz debe
  parecerse a Odoo con la identidad Provecho, no a la estética por defecto
  de un kit; partir de primitivas sin estilo (Base UI) da control total sin
  pelear contra un tema ajeno.
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
