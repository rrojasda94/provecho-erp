# Contexto para trabajar en frontend

Leer antes: `/CLAUDE.md`, [product/ui-ux.md](../product/ui-ux.md) y
[ADR-013 — Arquitectura frontend](../architecture/adr/ADR-013-arquitectura-frontend.md).

## Reglas duras

- **Tailwind CSS** para estilos, sobre los tokens de `frontend/app/globals.css`
  mapeados en `tailwind.config.ts` (`bg-primary` → `var(--color-primary)`) —
  nunca hex ni tamaño mágico, ni en CSS ni en className (PDV/Kiosk re-tematizan
  por marca pisando las variables; el resto de módulos usa Provecho/Majambo).
- **shadcn/ui** (componentes copiados a `components/ui/`, no una librería
  instalada) para overlays/interacción con reglas de accesibilidad no
  triviales (dialog, combobox, popover, tooltip, tabs/menu) y el catálogo
  base (Button, Input, Select, Card, Badge...) — corre sobre **Base UI**
  (nunca Radix). Podar el catálogo por defecto a lo que el ERP usa, nunca
  copiar el registro completo. Tarjetas/grillas simples sin comportamiento
  interactivo siguen siendo HTML + Tailwind sin componente.
- **Shell estilo Odoo**: home de apps (grilla de módulos, `app/(app)/apps.config.ts`)
  + navegación con sidebar dentro de cada módulo. Un módulo solo aparece en
  el grid, y solo es accesible por URL directa, si `permisos` (de
  `GET /users/me`) cubre su prefijo — el filtro del grid es UX, el guard real
  vive en el `layout.tsx` de cada módulo (server-side, deny por defecto,
  igual que el backend).
- **Color con moderación** (2026-07-27, revisado 2026-08-07): superficies
  neutras por defecto — acero `--color-steel` en el back office, blanco en las
  tarjetas, crema **solo** en PDV/KDS/login. El color de marca
  (`--color-primary`) se reserva para acción primaria y alertas. Nada de un
  color por tarjeta o por módulo.
- **Un acento, no una paleta por área** (revisado 2026-08-12, ADR-037): `--hue`
  aparece en reposo solo donde marca **estado** — el ítem activo del sidebar y
  el filo del rótulo de área. Todo lo demás arranca neutro y se enciende al
  apuntarlo. Se probó un color por área de negocio y se descartó: es el mismo
  arcoíris que ADR-013 §8 rechazó, con menos pasos.
- **Un estado nunca se comunica solo por color**: usar `Insignia` de
  `components/estado/insignia.tsx`, que ata el ícono al tono. Los colores
  salen de `--status-success/danger/warning/info`, nunca de `bg-accent/30` a
  mano — esos no tienen variante de alto contraste ni de modo oscuro.
- **Modo oscuro y accesibilidad**: los tokens ya están; una pantalla nueva no
  hace nada especial mientras use roles (`bg-card`, `text-muted-foreground`) y
  no colores de marca directos. No usar `next-themes` ni `localStorage` para
  preferencias: viven en el perfil y las escribe el layout raíz.
- **Tipografía**: Archivo para títulos y texto (los `h1`–`h4` ya heredan ancho
  92% y peso 600 — no agregar `italic` ni `uppercase`), `.cifra` (IBM Plex
  Mono) para importes, cantidades, códigos e IDs, `.logotipo` (Anton) solo
  para el wordmark.
- **Movimiento**: una sola curva, `var(--transicion)`. Entrada de pantalla,
  escalonado de grilla (`.revelar-lista`), filo del acento y estados. Nada que
  retrase una acción; `prefers-reduced-motion` ya está resuelto globalmente en
  `globals.css`, no reimplementarlo por componente. Sin librería de animación:
  si algo no sale con keyframes CSS o con los `data-starting-style` /
  `data-ending-style` de Base UI, discutirlo antes de instalar nada.
- **Moldes antes que pantallas**: una lista va con `TablaDatos` (28 pantallas
  la usan) y un alta o edición con `DialogoFormulario` (17). Marcar
  `meta.numero` en toda columna de importes o cantidades. Una pantalla nueva
  con su propia tabla o su propio `<dialog>` es deuda desde el primer día.
- **Registrar la pantalla en `lib/navegacion.ts`**, no en su `layout.tsx`: de
  ahí salen el sidebar y la paleta de comandos. Una pantalla sin registrar
  existe pero no se puede buscar.
- **Un `loading.tsx` por módulo**. Sin él el clic en el sidebar no acusa
  recibo hasta que el servidor termina, y se lee como que la aplicación se
  colgó.
- **Íconos**: `lucide-react`, tamaño 15–18 y `strokeWidth` 1.75, siempre
  `aria-hidden` con una etiqueta de texto al lado. Sin emoji en la UI: cada
  sistema los dibuja distinto.
- Responsive siempre (webapp + Android táctil vía PWA, no app nativa —
  ADR-013); táctil obligatorio en PDV/Kiosk/KDS/Inventario, el resto de
  módulos es PC-first pero igual responsive.
- Accesibilidad: paleta alternativa (daltonismo) y tamaño de fuente
  ajustable, ambos como preferencia del perfil del usuario, combinables
  con el tema de marca activo.
- Server Components por defecto; Client Component (`"use client"`) solo
  donde hay estado real (dialogs, carrito, buscador). Sin librería de
  estado global mientras `useState`/`useReducer` alcance.
- TypeScript estricto; componentes en PascalCase; App Router de Next.js.
- Datos solo de la API REST — sin lógica de negocio en el front. El navegador
  **nunca** llama a la API directo: sale por `app/api/proxy` (la CSP de
  `middleware.ts` fija `connect-src 'self'`), y el proceso de Next usa
  `API_INTERNAL_URL`. No existe `NEXT_PUBLIC_API_URL`.

## Checklist

- [ ] `npm run lint`, `npm run typecheck`, `npm test` y `npm run build` limpios.
- [ ] Probado en viewport móvil y desktop.
- [ ] Sin colores/tamaños mágicos fuera de los tokens de `globals.css`.
- [ ] Si el módulo es nuevo: agregado a `frontend/lib/modulos.ts` con su
      prefijo de permiso **y su área**, y `layout.tsx` propio con guard
      server-side.
- [ ] Flujo crítico nuevo (venta, cobro, login) cubierto con un test de
      Playwright.
