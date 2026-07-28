# F2 — Arquitectura de Frontend y UX

Documento maestro del frontend de Provecho ERP. Se refina de forma
incremental (cada sesión puede profundizar una sección) pero siempre se
devuelve completo — igual que `ROADMAP.md` para el backend.

Relación con otros documentos: `product/ui-ux.md` fija branding y reglas de
UX de negocio (qué se ve); este documento fija cómo se construye (código,
arquitectura, componentes). `prompts/frontend.md` resume las reglas duras
para un agente que va a tocar código. Antes de implementar cualquier
sección marcada ⬜, cerrar la spec aquí primero (regla de flujo de trabajo
de `/CLAUDE.md`).

Leyenda: ✅ decidido e implementado · 🔶 decidido, sin implementar (o
parcial) · ⬜ sin decidir.

Estado real de código al momento de escribir esto (2026-07-27): Next.js 15 /
React 19 / TypeScript, App Router. Existen dos rutas (`/login`, `/dashboard`),
`lib/api.ts` (fetch tipado server-side) y `lib/auth.ts` (cookie de sesión).
Sin librería de componentes, sin gestor de estado, sin capa de theming, sin
tests de frontend.

**Actualización 2026-07-27 (misma fecha, sesión distinta): ADR-013**
(`docs/architecture/adr/ADR-013-arquitectura-frontend.md`) resolvió 5 de
las 6 prioridades que este documento marcaba como bloqueantes del alfa:
Tailwind CSS sobre los tokens existentes, Base UI (no Radix, no kit
estilizado) como primitivas de interacción, shell de home de apps +
sidebar por módulo (patrón Odoo), permisos visuales vía `permisos` de
`GET /users/me` con guard server-side por `layout.tsx`, arquitectura de
carpetas por módulo, sin librería de estado global (confirmado), Android
como PWA/responsive (no nativo), y Playwright para e2e. Las secciones de
abajo ya reflejan esas decisiones — la única prioridad que seguía abierta
es **F2.11 Tablas** (elegir librería). Ver el resumen final actualizado.

## F2.1 Filosofía del frontend

**Decidido** (`product/ui-ux.md`): Desktop-first para back-office
(compras/contabilidad/comercial/RRHH/gerencia/marketing), táctil obligatorio
en PDV/Kiosk/KDS/Inventario (deben funcionar con mouse+teclado y con touch,
sin interacciones hover-only). Responsive en todo el ERP.

**Offline**: no es "modo offline de frontend" (service worker + cache local)
— es arquitectura de **hub local por sucursal** (ADR-009, ya implementado en
backend fases 1-2): los clientes (web/Android/PC) le hablan siempre al hub
por LAN, nunca directo a la nube ni a un cache local propio. El frontend no
necesita lógica de offline propia; necesita saber hablarle al hub (mismo
contrato REST que la nube).

✅ **Resuelto (ADR-013)**: PWA/responsive, no app nativa. Una sola base de
código (Next.js) para web y Android — descartado React Native/Kotlin
porque el requisito real es táctil en tablet, no acceso a hardware nativo.

⬜ Usuarios simultáneos / pestañas abiertas por sucursal: sin definir
formalmente (relevante para F2.18 tiempo real y F2.30).

## F2.2 Arquitectura del proyecto

✅ **Resuelto (ADR-013)**. Convención de carpetas por módulo, replicando
la modularidad que el backend ya tiene por Clean Architecture:

```
frontend/app/
  (auth)/login/
  (app)/
    layout.tsx          # lee /users/me una vez, guarda sesión+permisos en contexto
    page.tsx            # home de apps (grilla filtrada por permiso)
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

Un módulo de frontend no importa componentes internos de otro, solo lo
compartido en `components/` — mismo principio de bajo acoplamiento que
`src/modules/` en el backend. Sin implementar todavía (hoy sigue siendo
solo `app/` + `lib/`).

## F2.3 Sistema de diseño (tokens)

🔶 **Parcial**. Ya en código (`frontend/app/globals.css`): paleta de color
(`--color-primary/secondary/dark/cream/accent/gray`) y tipografías (Anton
Italic para títulos, Inter para cuerpo). Regla ya vigente: colores/fuentes
**solo** vía tokens CSS, nunca hex hardcodeado en componentes
(`prompts/frontend.md`).

⬜ **Falta tokenizar**: spacing, radius (hoy `8px`/`16px` sueltos en
`globals.css`), sombras/elevación, duración/easing de animaciones,
iconografía (sin librería de íconos elegida todavía), ilustraciones,
estados (hover/focus/disabled ya existen ad-hoc por selector CSS, no como
tokens nombrados).

## F2.4 Componentes base

✅ **Resuelto (ADR-013)**: Tailwind CSS (consumiendo los tokens de
`globals.css` vía `tailwind.config.ts`, nunca hex fijo) + **Base UI**
(`@base-ui-components/react`, no Radix, no kit estilizado como shadcn/ui)
para lo que necesita comportamiento accesible no trivial — dialog,
combobox, popover, tooltip, tabs/menu. Todo lo demás (tarjetas, grillas,
botones simples) es HTML + Tailwind sin librería. Sin implementación de
código todavía — sigue sin existir ni un `Button` propio (el login usa
HTML plano con CSS directa); el catálogo mínimo v1 (Button, Input, Select,
Checkbox, Switch, Card, Modal/Dialog, Tabs, Toast, Badge, Skeleton,
EmptyState, ErrorState) se construye sobre esta base ahora que está
decidida. Tabla (F2.11) sigue como decisión aparte — ninguna librería de
tablas resuelve accesibilidad de overlays, es un problema distinto.

## F2.5 Componentes especializados del ERP

⬜ **Sin empezar**, y depende de F2.4. Primeros candidatos reales por orden
de aparición en el backend: Ticket/Carrito POS y tarjeta de KDS (ya hay
contrato en `sales` — pantallas, `estado_preparacion`), tarjeta de producto
con dialog de personalización (ya especificado en `ui-ux.md`), tabla de
stock/inventario. El resto (receta, subreceta, lote, proveedor, factura,
guía, merma) se construye cuando su módulo backend tenga pantalla asignada.

## F2.6 Layout general

✅ **Resuelto (ADR-013)**: patrón Odoo en dos niveles. **(a) Home de apps**
(`/` tras login): grilla de íconos por módulo de negocio, filtrada por
`permisos` de `GET /users/me` (Server Component, sin llamada extra al
backend — el endpoint ya existe). **(b) Dentro de un módulo**: sidebar
vertical con el submenú del módulo activo + breadcrumb arriba (el
breadcrumb sigue siendo ruta de navegación del usuario, no árbol de menú —
`ui-ux.md`). Dirección visual: superficies neutras por defecto,
`--color-primary`/`--color-accent` reservados para acción primaria/ítem
activo — no un color de marca distinto por tarjeta. PDV/Kiosk no está
resuelto explícitamente por este ADR (su shell de pantalla completa queda
para cuando se construya esa pantalla). Sin implementar todavía — el
dashboard actual sigue siendo standalone.

## F2.7 Navegación

🔶 **Parcial**. Decidido y documentado (`ui-ux.md`): breadcrumb por **ruta
recorrida** (patrón Odoo), no por jerarquía; navegación jerárquica va por
menú desplegable, son mecanismos separados que no se mezclan.

✅ **Rutas protegidas por permiso — resuelto (ADR-013)**: cada
`layout.tsx` de módulo (`app/(app)/[modulo]/layout.tsx`) repite el chequeo
de permiso que ya filtra el home — el filtro del grid es solo UX, el
guard real es server-side, igual que el backend ya deniega por defecto
(`require_permission`). Ver F2.28.

⬜ **Sigue pendiente**: deep links, historial, favoritos, pantallas
recientes, búsqueda global (ya tiene spec de negocio en `ui-ux.md` —
contextual, por nombre/insumo/exclusión — falta decidir su implementación
de UI). Límite de eslabones del breadcrumb antes de colapsar: sin definir
con el negocio (pendiente ya registrado en `ui-ux.md`).

## F2.8 Gestión del estado

✅ **Resuelto (ADR-013)**: sin librería de estado global (Zustand/Redux)
mientras no aparezca un caso real que lo justifique (candidato futuro:
carrito de PDV compartido entre listado y dialog de cobro, si crece
mucho) — YAGNI explícito, ya no una recomendación a validar. Server
Components para todo lo de solo lectura (dashboard, listados de
back-office); Client Components (`"use client"`) solo donde hay
interacción real (PDV, Kiosk, KDS), con `useState`/`useReducer` de React.

## F2.9 Comunicación con backend

🔶 **Parcial**. REST vía `lib/api.ts` (`apiFetch`) ya funciona
(server-side, con manejo de error tipado `ApiError`). El backend ya soporta
idempotencia (`idempotency_key`/`id` client-generado en ventas/pagos/
movimientos — ADR-009 fase 2), así que el frontend puede confiar en
reintentos seguros cuando se necesiten.

⬜ **Sin decidir**: WebSockets/SSE (KDS tiempo real hoy sería polling según
`ROADMAP.md` — WS/Redis pub-sub es la vía documentada pero no implementada
en backend todavía), cache/invalidación en cliente, cancelación de
requests, batch requests. No bloquean el alfa si el alcance inicial es
back-office (sin tiempo real crítico); si el PDV/KDS entra al alfa, esto
sube de prioridad.

## F2.10 Manejo de errores

🔶 **Parcial**. `ApiError` ya distingue status HTTP; `dashboard/page.tsx`
ya diferencia 401 (redirect a login) de 403 (mensaje de permiso) de otros
(mensaje genérico "no se pudo cargar"). Patrón a repetir, no a rediseñar.

⬜ **Falta**: página de error global de Next.js (`error.tsx`/`not-found.tsx`
no existen todavía), componente `EmptyState`/`ErrorState` reutilizable
(F2.4), estrategia de retry visible al usuario (hoy es "recargar" implícito).

## F2.11 Tablas

⬜ **Sin empezar.** Ninguna tabla construida — es probablemente el
componente más usado de todo el ERP (inventario, ventas, compras,
proveedores, usuarios...). **Viable e importante cerrar su spec antes del
alfa**: qué librería (TanStack Table es la elección estándar para
React/Next sin atarse a un design system completo) y qué subconjunto de
funcionalidad entra en v1 (orden, filtro, búsqueda, paginación) vs. v2
(congelar/mover/ocultar columnas, selección + acciones masivas, scroll
virtual, totales) — no se necesita todo de entrada.

## F2.12 Formularios

⬜ **Sin empezar** más allá del login (formulario simple, sin librería).
Ya hay una regla de negocio que los afecta a todos: **tooltip de ayuda por
campo** (`ui-ux.md`) — todo formulario nuevo debe nacer con esto, no
agregarse después. Autoguardado/undo/redo/drafts: diferible hasta que un
formulario largo (ej. orden de compra, ficha de producto) lo justifique.

## F2.13 Experiencia de usuario (UX)

🔶 Ya hay 3 flujos de negocio especificados en `ui-ux.md` con reglas
concretas (no solo estética): dialog de personalización de producto en
PDV/Kiosk, dialog de upsell al ir al carrito, buscador contextual con
ranking por historial de uso. Son el input real de diseño visual — el
alfa no debería diseñar pantallas de PDV sin releer esas tres secciones.

## F2.14 Accesibilidad

🔶 **Decidido, sin implementar** (`ui-ux.md`): paleta alternativa
(daltonismo) + tamaño de fuente ajustable, ambos guardados en el **perfil
del usuario** (no en el dispositivo), combinables con el tema de marca
activo. Catálogo ya definido (2026-07-27): dos paletas (Provecho estándar
+ un modo alto contraste/daltonismo inspirado en Okabe-Ito, tokens
`--status-success/danger/warning/info`) y 4 niveles de tamaño de fuente
vía `--font-scale` (1.0/1.15/1.3/1.5) — ver `ui-ux.md#accesibilidad`. Ya
no bloquea implementar; sigue sin construirse.

## F2.15 Internacionalización

⬜ **No es prioridad para el alfa.** El grupo opera solo en Perú, español,
soles. No hay decisión formal de librería i18n — diferir hasta que haya
necesidad real (otro país/moneda), evitando el costo de abstraer un
sistema de traducciones para un solo idioma (YAGNI).

## F2.16 Seguridad del frontend

🔶 **Parcial**. JWT + refresh + Argon2id ya en backend; cookie de sesión ya
implementada (`lib/auth.ts`, `decodificarClaims`). Protección de rutas por
autenticación ya existe (redirect a `/login` sin cookie).

⬜ **Falta**: Content-Security-Policy (deuda ya declarada en
`ROADMAP.md` → Seguridad — "falta definirla junto con el frontend"),
expiración de sesión visible al usuario (hoy silenciosa hasta el próximo
request fallido), sanitización explícita de inputs que se rendericen
como HTML (ninguno hoy, revisar cuando aparezca contenido enriquecido —
ej. notas, comentarios). Ocultar módulo/ruta completa por permiso ya está
resuelto a nivel de layout (ADR-013, ver F2.28) — lo que falta es el nivel
más fino: ocultar/deshabilitar un botón o acción puntual dentro de una
pantalla ya visible.

## F2.17 Rendimiento

🔶 Lazy loading y code splitting vienen gratis con App Router de Next.js
(no requieren decisión). ⬜ Sin definir: presupuesto de bundle, análisis
periódico, prefetch de rutas críticas (POS), optimización de imágenes
(ninguna imagen real todavía — logo/branding pendiente de asset final).
No es bloqueante para el alfa; revisar cuando el bundle crezca con F2.4/F2.5.

## F2.18 Tiempo real

⬜ **Sin implementar en frontend.** El backend ya tiene el dato que
necesita tiempo real (`venta_item.estado_preparacion` para KDS,
`apertura_caja`/`cierre_caja` para caja) pero lo sirve por REST simple. Vía
documentada (`ROADMAP.md` → deuda de `sales`): WebSocket/Redis pub-sub,
todavía no construido ni en backend ni en frontend. Si KDS entra al alfa,
el primer corte viable es **polling** (ya es lo que el propio ROADMAP
asume como estado actual) y WS queda para después — no bloquear el alfa
por esto.

## F2.19 Auditoría del cliente

⬜ **Sin decidir.** El backend ya audita acciones de servidor (`audit_log`,
tres flujos de log). Auditoría de navegación/interacción del lado
cliente (qué pantalla vio, cuánto tiempo) no está especificada — evaluar si
el negocio realmente lo necesita antes de construirlo (no está en ningún
requisito de negocio documentado hoy).

## F2.20 Notificaciones

⬜ **Sin decidir**, y depende de que exista el módulo de notificaciones en
backend (hoy ⬜ en `ROADMAP.md`: "Celery + canales por definir"). Toast de
UI (confirmaciones síncronas de una acción) es independiente de eso y se
puede construir con F2.4 sin esperar al backend.

## F2.21 Dashboard

✅ **Primer dashboard ya implementado** (`app/dashboard/page.tsx`): 3
tarjetas (ventas del día, stock bajo mínimo, cajas abiertas) contra
`GET /api/v1/dashboard/resumen` (ADR-012). Es deliberadamente mínimo — ver
`ROADMAP.md` → deuda de Dashboard y caja para la lista de indicadores
futuros (serie por hora, ranking de productos, alertas de KDS demorado).
Sin widgets configurables, sin drill-down, sin gráficos todavía.

## F2.22 Personalización

⬜ **Sin empezar** más allá de lo ya decidido en F2.14 (accesibilidad en
perfil de usuario) y el mecanismo de theming de marca (F2.3/F2.14, deuda
técnica ya declarada). Densidad de tabla, columnas guardadas, atajos
personalizados: diferible.

## F2.23 Impresión

⬜ **Sin empezar en frontend.** El backend ya genera comanda de KDS
imprimible (texto 32 columnas, contador de reimpresiones) y comprobante vía
Factiliza (boleta/factura), pero **la descarga de PDF/XML/CDR del
comprobante emitido no está implementada** (deuda ya declarada en
`ROADMAP.md` → `sales`). El frontend no puede ofrecer "vista previa /
imprimir factura" hasta que ese endpoint exista.

## F2.24 Integración con hardware

⬜ **Sin decidir.** Impresora térmica ESC/POS para KDS: deuda ya declarada
en `ROADMAP.md` (puente por red o agente local, sin construir). Lectores
QR/código de barras, balanzas, tablets, kioskos: sin especificar todavía —
se define cuando exista el primer cliente PDV real, no antes (evitar
diseñar hardware para un flujo que aún no tiene pantalla).

## F2.25 Testing

🔶 **Parcial (ADR-013)**: Playwright adoptado para e2e de flujos críticos
(login, filtrado del home de apps por permiso, crear venta, cobrar) —
prioriza flujos de plata sobre cobertura unitaria de componentes sueltos.
⬜ Sin implementar todavía (cero tests de frontend hoy) y sin decidir
testing unitario de componentes/hooks (candidato: Vitest + Testing
Library cuando exista F2.4). No bloquea el alfa si es una demo guiada,
pero sí antes de producción real con dinero de por medio (POS).

## F2.26 Observabilidad

⬜ **Sin empezar en frontend.** Backend ya tiene Sentry/GlitchTip listo
(`core/sentry.py`, sin DSN configurado — deuda ya declarada). Extender el
mismo Sentry SDK al frontend (Next.js tiene integración oficial) es la
vía natural cuando se decida el proveedor — no es una decisión nueva,
es reusar la de `ADR-006`.

## F2.27 Mantenibilidad

🔶 **Parcial**. ESLint ya configurado (`frontend/.eslintrc.json`) y exigido
antes de commit (`/CLAUDE.md`). TypeScript estricto y PascalCase para
componentes ya son regla (`prompts/frontend.md`, actualizado con las
reglas técnicas de ADR-013). Convención de carpetas por módulo ya decidida
(F2.2). ⬜ Sin Storybook, sin checklist de PR específico de frontend
(existe el general de `/CLAUDE.md`).

## F2.28 Permisos visuales por rol *(agregado local)*

✅ **Resuelto (ADR-013)**. `GET /users/me` ya devuelve `permisos: string[]`
(lista plana de códigos, sin cambio de backend necesario). El home de apps
filtra qué módulos se muestran (`appsVisibles(permisos)` contra un
registro estático módulo→prefijo de permiso); cada `layout.tsx` de módulo
repite el check server-side — el filtro del grid es UX, no el único gate
(descartado explícitamente "permisos resueltos solo en el cliente").
Pendiente más fino: ocultar/deshabilitar una acción puntual dentro de una
pantalla ya visible (ver F2.16) — el patrón de módulo/ruta está resuelto,
el de botón/acción no.

## F2.29 Sistema de productividad *(agregado local)*

⬜ **Sin decidir.** Atajos de teclado, Command Palette, navegación rápida:
nada construido. Razonable de diferir — valioso para el usuario de 8-10h
(cajero, cocinero) pero no bloquea que el alfa funcione. Revisar cuando el
POS tenga su primer flujo real (ahí es donde más se nota la fricción de
clics).

## F2.30 Gestión de ventanas y multitarea *(agregado local)*

⬜ **Sin decidir**, y relacionado con F2.1 (múltiples pestañas/sucursal).
Recuperación de estado al recargar (ej. carrito a medio armar) depende de
F2.8. Diferible hasta que el PDV real exponga el problema concreto.

## F2.31 Microinteracciones y feedback *(agregado local)*

⬜ **Sin empezar.** Indicadores de guardado/sincronización/estados de
carga: ninguno construido (el dashboard hoy no tiene ni loading skeleton).
Entra naturalmente con F2.4 (Skeleton, Toast) — no es una sección aparte
que requiera su propia decisión previa.

## Resumen — qué cerrar antes de los diseños finales del alfa

**Actualizado 2026-07-27 tras ADR-013**: de las 6 prioridades originales,
5 ya están resueltas (layout, componentes base, permisos visuales,
arquitectura de carpetas, estado). Queda una sola bloqueante real:

1. **F2.11 Tablas** — elegir librería (candidata: TanStack Table) y
   alcance v1 (orden/filtro/búsqueda/paginación) vs. v2 (columnas
   congelar/mover/ocultar, selección + acciones masivas, scroll virtual,
   totales). Es el componente más usado de todo el ERP y ninguna tabla
   está construida todavía — el único hueco de arquitectura que ADR-013
   no cubrió (resuelve overlays/interacción, no grillas de datos).

Resueltas por ADR-013 (`docs/architecture/adr/ADR-013-arquitectura-frontend.md`),
sin implementar todavía en código: F2.6 (home de apps + sidebar estilo
Odoo), F2.4 (Tailwind + Base UI), F2.28 (permisos vía `/users/me` +
guard por `layout.tsx`), F2.2 (carpetas por módulo), F2.8 (sin
Zustand/Redux, confirmado), más F2.1 (Android = PWA/responsive) y F2.25
(Playwright para e2e).

El resto de las 31 secciones tiene decisión tomada, está correctamente
diferido, o depende de un módulo backend que todavía no llega a pantalla —
no bloquean empezar a diseñar.
