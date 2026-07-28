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
- **Color con moderación** (2026-07-27): superficies neutras por defecto
  (blanco/gris/crema) — el color de marca (`--color-primary`/`--color-accent`)
  se reserva para acción primaria, estado activo/seleccionado y alertas, no
  para pintar cada tarjeta/módulo de un color distinto. Moderno y funcional
  antes que colorido; la identidad de marca vive en tipografía + un acento
  consistente, no en un arcoíris de superficies.
- Anton Italic para titulares (h1–h4 ya lo heredan), Inter para texto.
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
- Datos solo de la API REST (`NEXT_PUBLIC_API_URL`) — sin lógica de negocio en el front.

## Checklist

- [ ] `npm run lint` y `npm run build` limpios.
- [ ] Probado en viewport móvil y desktop.
- [ ] Sin colores/tamaños mágicos fuera de tokens/`tailwind.config.ts`.
- [ ] Si el módulo es nuevo: agregado a `apps.config.ts` con su prefijo de
      permiso, y `layout.tsx` propio con guard server-side.
- [ ] Flujo crítico nuevo (venta, cobro, login) cubierto con un test de
      Playwright.
