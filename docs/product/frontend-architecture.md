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

⬜ **Pendiente**: PWA vs. app nativa/React Native para Android 15+
(`tech-stack.md` lo deja abierto). Cualquiera de las dos opciones habla con
el hub, así que no bloquea el resto de la arquitectura — pero sí decide si
hay un segundo proyecto (nativo) o un solo Next.js con manifest+service
worker de instalación (PWA).

⬜ Usuarios simultáneos / pestañas abiertas por sucursal: sin definir
formalmente (relevante para F2.18 tiempo real y F2.30).

## F2.2 Arquitectura del proyecto

🔶 **Parcial**. Hoy: `frontend/app/` (rutas) + `frontend/lib/` (fetch +
auth). Sin `components/`, `hooks/`, `store/`, `types/`, `constants/`.

**Propuesta para el plan** (a validar al construir la primera pantalla
nueva, no antes):

```
frontend/
  app/            # rutas (App Router) — solo composición de página
  components/
    ui/           # componentes base (F2.4) — sin lógica de negocio
    erp/          # componentes especializados (F2.5)
    layout/       # sidebar, topbar, breadcrumb (F2.6)
  hooks/          # hooks compartidos (useTablero, useAtajos, etc.)
  lib/            # api.ts, auth.ts — infraestructura de datos, ya existe
  store/          # estado global cliente, si aparece (F2.8)
  styles/         # tokens si crecen más allá de globals.css
  types/          # tipos compartidos entre rutas (hoy inline por página)
```

No se crea carpeta hasta que la necesidad sea real (regla KISS de
`/CLAUDE.md`) — esto es el destino, no algo a scaffoldear todo de una vez.

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

⬜ **Sin empezar.** No existe ni un `Button`/`Input` propio — el login usa
`<button>`/`<input>` con clases CSS directas. Es el hueco más urgente antes
de construir cualquier pantalla nueva: cada pantalla que se agregue sin
esto reinventa estilos y duplica CSS (contradice DRY de `/CLAUDE.md`).

**Viable para el plan**: catálogo mínimo antes del alfa — Button, Input,
Select, Checkbox, Switch, Card, Modal/Dialog, Tabs, Toast, Badge, Table
(base), Skeleton, EmptyState, ErrorState. El resto de la lista larga
(Command Palette, DatePicker/Calendar propios, etc.) se agrega bajo demanda
cuando una pantalla real lo pida — no antes (YAGNI).

## F2.5 Componentes especializados del ERP

⬜ **Sin empezar**, y depende de F2.4. Primeros candidatos reales por orden
de aparición en el backend: Ticket/Carrito POS y tarjeta de KDS (ya hay
contrato en `sales` — pantallas, `estado_preparacion`), tarjeta de producto
con dialog de personalización (ya especificado en `ui-ux.md`), tabla de
stock/inventario. El resto (receta, subreceta, lote, proveedor, factura,
guía, merma) se construye cuando su módulo backend tenga pantalla asignada.

## F2.6 Layout general

⬜ **Sin empezar.** El dashboard actual es standalone (sin sidebar/topbar).
Antes de agregar una segunda pantalla de back-office hace falta decidir el
shell: sidebar de navegación + topbar (usuario, sucursal activa, logout) +
área de trabajo. PDV/Kiosk probablemente necesitan su propio shell
(pantalla completa, sin sidebar) — **decidir si es un layout de Next.js
distinto (`app/(pdv)/layout.tsx` vs `app/(backoffice)/layout.tsx`) antes de
construir POS**, para no migrar rutas después.

## F2.7 Navegación

🔶 **Parcial**. Decidido y documentado (`ui-ux.md`): breadcrumb por **ruta
recorrida** (patrón Odoo), no por jerarquía; navegación jerárquica va por
menú desplegable, son mecanismos separados que no se mezclan.

⬜ **Pendiente**: rutas protegidas por permiso (hoy solo hay redirect por
falta de cookie, no hay chequeo de `permiso` en frontend — ver F2.28),
deep links, historial, favoritos, pantallas recientes, búsqueda global (esta
última ya tiene spec de negocio en `ui-ux.md` — contextual, por
nombre/insumo/exclusión — falta decidir su implementación de UI).
Límite de eslabones del breadcrumb antes de colapsar: sin definir con el
negocio (pendiente ya registrado en `ui-ux.md`).

## F2.8 Gestión del estado

⬜ **Sin decidir formalmente.** Hoy todo es Server Components + Server
Actions (login, logout) — cero estado de cliente. Esto alcanza mientras las
pantallas sean de solo lectura/formularios simples. Se vuelve una decisión
real en cuanto exista el carrito POS (estado que sobrevive varias
interacciones antes de un submit) o filtros/estado de tabla que no deben
perderse al navegar.

**Recomendación a validar con el usuario**: no traer Redux/Zustand hasta
que el carrito POS lo exija — mientras tanto, `useState`/`useReducer` local
por componente alcanza (YAGNI). Cuando el carrito exista, evaluar Zustand
(simple, sin boilerplate) frente a seguir con Context — decisión puntual,
no ahora.

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
activo. ⬜ Pendiente con el negocio: catálogo exacto de paletas alternativas
y cuántos niveles de tamaño de fuente (bloquea implementar, no bloquea
diseñar el mecanismo).

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
ocultar acciones por permiso en UI (F2.28), expiración de sesión visible al
usuario (hoy silenciosa hasta el próximo request fallido), sanitización
explícita de inputs que se rendericen como HTML (ninguno hoy, revisar
cuando aparezca contenido enriquecido — ej. notas, comentarios).

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

⬜ **Sin empezar.** Cero tests de frontend hoy (ni unitarios ni E2E). Se
propone: Vitest + Testing Library para componentes/hooks desde que exista
F2.4 (probar el sistema de diseño primero, no las pantallas), Playwright
para E2E cuando exista un flujo crítico completo (login → dashboard, luego
venta completa). No bloquea el alfa si el alfa es una demo guiada, pero sí
antes de producción real con dinero de por medio (POS).

## F2.26 Observabilidad

⬜ **Sin empezar en frontend.** Backend ya tiene Sentry/GlitchTip listo
(`core/sentry.py`, sin DSN configurado — deuda ya declarada). Extender el
mismo Sentry SDK al frontend (Next.js tiene integración oficial) es la
vía natural cuando se decida el proveedor — no es una decisión nueva,
es reusar la de `ADR-006`.

## F2.27 Mantenibilidad

🔶 **Parcial**. ESLint ya configurado (`frontend/.eslintrc.json`) y exigido
antes de commit (`/CLAUDE.md`). TypeScript estricto y PascalCase para
componentes ya son regla (`prompts/frontend.md`). ⬜ Sin Storybook, sin
convención de nombres de archivo documentada más allá de componentes,
sin checklist de PR específico de frontend (existe el general de
`/CLAUDE.md`).

## F2.28 Permisos visuales por rol *(agregado local)*

⬜ **Sin empezar, pero desbloqueado.** El RBAC completo ya existe en
backend (`users`: rol/permiso/usuario_rol/rol_permiso, `require_permission`
deny-by-default, `docs/security/authorization.md`). Falta decidir el
mapeo a UI: ¿los claims del JWT ya traen permisos resueltos para que el
frontend solo oculte/deshabilite, o el frontend debe llamar a `/me` y
cachear el set de permisos? **Viable cerrar esta spec antes del alfa** —
afecta cómo se diseña cada pantalla desde el principio (qué botón/acción
se oculta a qué rol), no algo que se pueda agregar después sin rehacer
componentes.

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

Orden sugerido (bloquean diseño visual, no son opcionales antes de dibujar
pantallas):

1. **F2.6 Layout general** — shell de back-office vs. shell de PDV/Kiosk.
2. **F2.4 Componentes base** — catálogo mínimo v1.
3. **F2.11 Tablas** — librería + alcance v1.
4. **F2.28 Permisos visuales** — mecanismo de mapeo rol→UI.
5. **F2.2 Arquitectura de carpetas** — antes de que la 3ª pantalla obligue
   a reordenar código ya escrito.
6. **F2.8 Estado** — al menos la decisión de "no Redux todavía", explícita.

El resto de las 31 secciones tiene decisión tomada, está correctamente
diferido, o depende de un módulo backend que todavía no llega a pantalla —
no bloquean empezar a diseñar.
