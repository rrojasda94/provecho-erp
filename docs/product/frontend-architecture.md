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
Tailwind CSS sobre los tokens existentes, shadcn/ui (sobre Base UI, no
Radix) como primitivas de interacción y catálogo base, shell de home de
apps + sidebar por módulo (patrón Odoo), permisos visuales vía `permisos`
de `GET /users/me` con guard server-side por `layout.tsx`, arquitectura de
carpetas por módulo, sin librería de estado global (confirmado), Android
como PWA/responsive (no nativo), y Playwright para e2e. Las secciones de
abajo ya reflejan esas decisiones — la única prioridad que seguía abierta
es **F2.11 Tablas** (elegir librería). Ver el resumen final actualizado.

**Actualización 2026-07-27 (segunda revisión, misma fecha)**: dentro de
ADR-013, la sección de primitivas de interacción cambió de Base UI directo
a **shadcn/ui** (sigue corriendo sobre Base UI, sigue sin Radix) — mejor
ajuste al objetivo de negocio de poder editar color y forma por marca
rápido (token set semántico + `--radius` único, en vez de construir el
catálogo de componentes a mano). Ver ADR-013 sección 2 para el detalle.

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
  ui/                    # componentes shadcn/ui (copiados, editables) sobre Base UI
  shell/                 # AppGrid, Sidebar, Breadcrumb — layout, no de un módulo
frontend/lib/
```

Un módulo de frontend no importa componentes internos de otro, solo lo
compartido en `components/` — mismo principio de bajo acoplamiento que
`src/modules/` en el backend. Sin implementar todavía (hoy sigue siendo
solo `app/` + `lib/`).

## F2.3 Sistema de diseño (tokens)

🔶 **Parcial**. Ya en código (`frontend/app/globals.css`):

- Paleta de color (`--color-primary/secondary/dark/cream/accent/gray/steel`),
  revisada el 2026-08-07 por contraste medido (ver `ui-ux.md`).
- Un **acento único** (`--hue`, sobre `--marca-primary`). El color por área de
  negocio se probó y se descartó el 2026-08-12 (ADR-037): ADR-013 §8 ya había
  rechazado el color por módulo o tarjeta. Las áreas siguen agrupando el home,
  sin pintar.
- **Estados semánticos**: `--status-success/danger/warning/info`, cada uno con
  su `-surface` para el relleno de insignia, y su variante de alto contraste y
  de modo oscuro.
- Tipografías: Archivo (variable, títulos y cuerpo), IBM Plex Mono (cifras,
  clase `.cifra`), Anton (solo logotipo, clase `.logotipo`).
- `--radius` (6px, un solo valor para todos los componentes) y `--transicion`
  (una curva para todo el ERP).
- Iconografía: `lucide-react`, ya usada por calendario, diálogos, reportes y
  el registro de módulos.

Regla ya vigente: colores/fuentes **solo** vía tokens CSS, nunca hex
hardcodeado en componentes (`prompts/frontend.md`).

- **Elevación**: `--sombra-1/2/3` (apoyada, flotante, interrumpe), teñidas con
  la tinta de marca y no con negro puro, con su juego para modo oscuro.
- **Escala tipográfica accesible**: `--font-scale` con sus cuatro niveles en
  `[data-escala]`.
- `@custom-variant dark (&:is(.dark *))` — **obligatorio**. Tailwind v4 no
  declara la variante `dark` por estrategia de clase: sin esa línea las
  decenas de clases `dark:` que `shadcn add` deja escritas en
  `components/ui/**` no compilan a nada, y el síntoma solo se ve en el
  navegador.

⬜ **Falta tokenizar**: spacing (la escala de Tailwind alcanza por ahora),
ilustraciones, y los estados hover/focus/disabled, que existen como clases de
componente (`.ficha`, `.nav-modulo`) y utilidades de Tailwind, no como tokens
nombrados.

## F2.4 Componentes base

✅ **Resuelto (ADR-013, revisado)**: Tailwind CSS (consumiendo los tokens
de `globals.css` vía `tailwind.config.ts`, nunca hex fijo) + **shadcn/ui**
sobre **Base UI** (no Radix) para lo que necesita comportamiento accesible
no trivial — dialog, combobox, popover, tooltip, tabs/menu — y el catálogo
base (Button, Input, Select, Checkbox, Switch, Card, Badge, Skeleton).
shadcn/ui no es una dependencia instalada: el CLI copia el código fuente a
`components/ui/`, queda en el repo y se edita directo. Se eligió sobre
construir a mano porque el token set semántico (`--primary`, `--muted`,
`--radius`...) que trae de fábrica es justo lo que hace fácil editar color
y forma por marca — objetivo real de negocio, no solo estética. Tarjetas/
grillas simples sin comportamiento interactivo siguen siendo HTML +
Tailwind sin componente. Sin implementación de código todavía — sigue sin
existir ni un `Button` propio (el login usa HTML plano con CSS directa).
Al correr `shadcn init`, podar el catálogo a lo que el ERP usa (no copiar
el registro completo) y remapear sus tokens genéricos a los 6 tokens de
marca de Provecho antes de aceptar el resultado por defecto — ver ADR-013
sección 1 y 2. Tabla (F2.11) sigue como decisión aparte — ninguna librería
de tablas resuelve accesibilidad de overlays, es un problema distinto.

## F2.5 Componentes especializados del ERP

🔶 **Parcial**. Ticket/Carrito POS (`app/pdv/ticket.tsx`, 2026-07-28) y
tarjeta de KDS (`app/kds/`, 2026-08-03) ya existen, construidos en su
pantalla y con CSS propio — no promovidos todavía a `components/` porque
hasta ahora ninguno tiene un segundo consumidor. Siguientes candidatos:
tarjeta de producto
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

El KDS (2026-08-03) agrega el patrón de **cliente desde el navegador**:
`lib/cliente-api.ts` (fetch + error tipado vía el proxy que adjunta el
token) compartido por PDV y KDS, con `lib/pdv.ts`/`lib/kds.ts` aportando
solo tipos y rutas. El **pad de asistencia** (`app/asistencia/`, 2026-08-24,
ADR-065) es la tercera pantalla táctil fuera del shell y entra por la misma
puerta: `lib/asistencia.ts` son tipos y rutas, y el pinpad es el mismo
componente del PDV.

⬜ **Sin decidir**: WebSockets/SSE. El KDS ya está en producción de código
con **polling cada 3 s** (`REFRESCO_MS`, pausado con la pestaña oculta) —
suficiente para que una pantalla vea lo que tachó otra, pero el push
(WS/Redis pub-sub) sigue sin implementar en backend. También sin decidir:
cache/invalidación en cliente, cancelación de
requests, batch requests. No bloquean el alfa si el alcance inicial es
back-office (sin tiempo real crítico); si el PDV/KDS entra al alfa, esto
sube de prioridad.

## F2.10 Manejo de errores

🔶 **Parcial**. `ApiError` ya distingue status HTTP; `obtenerSesion` maneja
el 401 (redirect a login).

✅ **Error ≠ vacío (2026-08-07)**. La regla, y es innegociable en pantallas
nuevas: **un fetch que falló nunca se dibuja como lista vacía**. El estado
vacío queda reservado para respuestas exitosas sin filas.

`lib/carga.ts` es el clasificador compartido —sin dependencias, probado con
`node --test` en `lib/carga.test.ts`—:

- `Falla = { mensaje, detalle, status }`. `mensaje` lo pone el llamador (lo
  lee el usuario), `detalle` es lo que dijo el servidor o la excepción (se
  muestra en letra chica, para poder diagnosticar sin abrir DevTools) y
  `status` es `null` cuando ni hubo respuesta — red caída, proxy, DNS.
- `fallaDe(e, mensaje)` lee el `status` por forma, no por `instanceof`: a un
  Server Component pueden llegarle tanto `ApiError` (`lib/api.ts`) como
  `ErrorApi` (`lib/cliente-api.ts`).
- `esSinPermiso(falla)` es **solo 403**. Un 403 se traga (el bloque no es
  del usuario); red, 5xx y 401 se muestran, porque "no se pudo preguntar" no
  es "no te toca".
- `Lista<T> = { datos, falla, recargar }` se pasa **entera** a los
  componentes: así ninguno puede renderizar las filas sin haber mirado la
  falla.

Aplicado en los dos lugares donde el patrón viejo (`.catch(() => setLista([]))`)
había hecho daño:

- **PDV** (`app/pdv/use-datos-pdv.ts` → `catalogo.tsx`): mesas, cobrados y
  órdenes en cocina muestran un panel `.pdv-fallo` con "Reintentar", que
  llama a la misma función que hace la carga inicial. Reintentar sin recargar
  la página importa acá: recargar el PDV pierde los borradores abiertos.
- **Dashboard** (`app/(app)/dashboard/page.tsx`): cada bloque sigue fallando
  por su cuenta, pero ahora `bloque()` separa 403 de fallo real y
  `components/shell/aviso-fallo.tsx` lista lo que no se pudo traer con un
  reintento (`router.refresh()` en `useTransition` — la pantalla se arma en
  el servidor).

⬜ **Falta**: página de error global de Next.js (`error.tsx`/`not-found.tsx`
no existen todavía) y unificar `.pdv-fallo` con `AvisoFallo` en un
`ErrorState` reutilizable (F2.4) — hoy son dos porque el PDV corre sobre su
paleta oscura propia y el shell sobre Tailwind. Quedan cargas del PDV con el
patrón viejo (carta, medios de pago, POS, caja): ver ROADMAP → Frontend.

## F2.11 Tablas

✅ **Resuelto (2026-08-02)**: **TanStack Table** (`@tanstack/react-table`,
headless — sin componentes propios, encaja con Tailwind y no ata a un
design system) para toda tabla del ERP. **v1** (implementado en el primer
listado real, `compras/proveedores`): orden por columna, búsqueda, filtro,
paginación. **v2, diferido hasta que una pantalla real lo necesite**:
congelar/mover/ocultar columnas, selección + acciones masivas, scroll
virtual, totales — TanStack Table ya soporta todo eso vía plugins, así que
no es una migración de librería, es prender la función cuando haga falta.
El componente reusable vive en `frontend/components/tabla/`.

## F2.12 Formularios

🔶 **Molde común desde el 2026-08-10**: `components/formulario/
dialogo-formulario.tsx`. Toda alta y toda corrección del ERP pasan por él —
`<dialog>` nativo, `useActionState`, el error del servidor en un
`role="alert"`, Cancelar/Guardar, y cerrar al `ok`. Antes ese bloque estaba
copiado en siete pantallas; con la edición encima habrían sido veinte
copias, y la que se olvidara de cerrar al `ok` iba a ser un bug sin relación
aparente con las otras diecinueve.

Sigue siendo `<dialog>` nativo y no el `Dialog` de shadcn: el overlay, el
foco atrapado y el cierre con Esc vienen del navegador, y ninguna pantalla
pidió todavía algo que eso no cubra. ADR-013 dejó shadcn instalado para
cuando haga falta, no para usarlo por defecto.

**Dos reglas que el componente hace cumplir por todos:**

1. **La acción se despacha a mano dentro de una transición, no por el prop
   `action` de `<form>`.** React 19 resetea solo el formulario cuando la
   acción va en `action`, y lo hace también cuando la acción devolvió error:
   un rechazo del servidor borraba todo lo tecleado. Reteclear un formulario
   entero porque un campo estaba mal es la fricción que termina en un dato
   inventado — es el mismo candado que `e2e/caja.spec.ts` ya probaba para el
   conteo de caja, ahora extendido a todo formulario.
2. **El reset va al cerrar, no al enviar.** Cancelar limpia; un error deja
   todo donde estaba.

Cada diálogo de edición además **dice qué no se puede cambiar y por qué**
(prop `ayuda`): la unidad de medida de un artículo, el `username` de una
cuenta, el código de una cuenta contable. Un campo ausente sin explicación se
lee como un olvido.

Sigue pendiente el **tooltip de ayuda por campo** (`ui-ux.md`) —hoy la ayuda
es a nivel de formulario, no de campo— y autoguardado/undo/redo/drafts,
diferibles hasta que un formulario largo (orden de compra, ficha de
producto) lo justifique.

## F2.13 Experiencia de usuario (UX)

🔶 Ya hay 3 flujos de negocio especificados en `ui-ux.md` con reglas
concretas (no solo estética): dialog de personalización de producto en
PDV/Kiosk, dialog de upsell al ir al carrito, buscador contextual con
ranking por historial de uso. Son el input real de diseño visual — el
alfa no debería diseñar pantallas de PDV sin releer esas tres secciones.

## F2.14 Accesibilidad

✅ **Implementado 2026-08-12 (ADR-037)**. Paleta alternativa (daltonismo
rojo-verde, Okabe-Ito), tamaño de fuente en cuatro niveles y modo oscuro, las
tres guardadas en el **perfil del usuario** (`preferencia_paleta`,
`preferencia_tamano_fuente`, `preferencia_tema`) y no en el dispositivo — en
un local la misma tablet la usan tres turnos.

Se resuelven en el servidor: el layout raíz lee `/users/me` y escribe
`class="dark"`, `data-escala` y `data-paleta` en `<html>`. No se usa
`next-themes` (instalado, pero solo alimenta a `sonner`): guarda en
`localStorage` y necesita un script inline antes del primer pintado, que la
CSP con nonce de `middleware.ts` tendría que autorizar. Sin parpadeo y sin
tocar la CSP.

Paleta y tema **se combinan**: `[data-paleta="alto-contraste"]` va declarado
después de `.dark` (misma especificidad, gana el último) y hay un
`.dark[data-paleta="alto-contraste"]` con los valores aclarados.

El ícono obligatorio por estado vive en `components/estado/insignia.tsx`,
atado al tono. `PATCH /users/me/preferencias` no exige permiso.

⬜ **Falta**: auditoría de contraste sobre las pantallas ya construidas
(los tokens cumplen AA; los pares que cada pantalla combina no se
verificaron uno por uno), navegación por teclado en el PDV y el KDS, y
lectores de pantalla.

## F2.15 Internacionalización

⬜ **No es prioridad para el alfa.** El grupo opera solo en Perú, español,
soles. No hay decisión formal de librería i18n — diferir hasta que haya
necesidad real (otro país/moneda), evitando el costo de abstraer un
sistema de traducciones para un solo idioma (YAGNI).

## F2.16 Seguridad del frontend

🔶 **Parcial**. JWT + refresh + Argon2id ya en backend; cookie de sesión ya
implementada (`lib/auth.ts`, `decodificarClaims`). Protección de rutas por
autenticación ya existe (redirect a `/login` sin cookie).

✅ **El PIN dejó de tener campo, también en el login** (2026-08-15, ADR-050,
enmienda a ADR-045). `app/login/page.tsx` lo pedía en un
`<input type="password" autocomplete="current-password">` — el patrón que
ADR-045 había eliminado dentro del PDV, con la etiqueta que le pide al
navegador que lo guarde. Hoy el usuario se teclea y el PIN se toca en
`components/pinpad/` (mudado desde `app/pdv/`, con su CSS a `globals.css` y
respaldo de tokens para las dos paletas); no queda ningún campo, ni oculto,
y una prueba e2e afirma el DOM para que el patrón no vuelva a colarse.
Además `loginAction` **distingue los tres rechazos** del servidor —401, 423
con sus 15 minutos, 429 con su `Retry-After`— y devuelve `{error, motivo}`
en vez de `e.message`: antes los tres llegaban con el mismo texto y las tres
salidas terminaban igual, probando de nuevo hasta bloquear la cuenta. Sigue
abierto `app/cambiar-pin/`, con sus tres campos (ver Deuda → Frontend).

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
✅ **7 casos en verde y en el job `e2e` de CI** (2026-08-06):
`frontend/e2e/caja.spec.ts` cubre abrir caja → vender → cobrar → cerrar,
RN-POS-011 y que un rechazo del servidor no borre lo tecleado;
`frontend/e2e/sesion.spec.ts` cubre login → cookie httpOnly → logout y el
**gate de módulo por permiso entrando por URL directa** (el filtro del home
es UX; lo que decide es el `layout.tsx`). Fuera del PDV, el resto de las
pantallas sigue sin prueba.
✅ **16 casos** (2026-08-15, ADR-050): `sesion.spec.ts` suma los tres del
login con pinpad — que **no exista ningún `input` de contraseña en el DOM**
(se afirma el DOM y no un comportamiento: un `type="password"` agregado sin
querer no rompería ninguna otra prueba), que un PIN equivocado no borre el
usuario tecleado, y que una cuenta bloqueada (423) avise distinto que un PIN
equivocado (401). El 429 no se prueba: `e2e/servidor-api.mjs` sube el rate
limit a propósito para que la suite entera pueda entrar desde la misma IP.
⬜ Sin decidir testing unitario de componentes/hooks (candidato: Vitest +
Testing Library cuando exista F2.4); los 14 casos de `npm test` corren a
mano y **no están en CI**. No bloquea el alfa si es una demo guiada, pero sí
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

🔶 **Paleta de comandos construida 2026-08-12 (ADR-037)**.
`components/shell/paleta-comandos.tsx`: `Ctrl+K` / `⌘K` abre un buscador de
pantallas sobre `@base-ui/react` Autocomplete + Dialog — sin `cmdk`, que
traería un motor de coincidencia difusa para ~50 entradas estáticas y el
árbol de Radix que ADR-013 descartó. Los destinos salen de
`lib/navegacion.ts`, se arman en el servidor y llegan **filtrados por
permiso**. Cada resultado es un `<Link>` de verdad: Enter, clic, clic central
y "abrir en pestaña nueva" funcionan sin programarlos.

La tabla suma `/` para enfocar su buscador.

⬜ **Falta**: atajos por acción dentro de una pantalla (guardar, nuevo,
siguiente fila) y comandos que ejecuten en vez de navegar. Se revisan cuando
el PDV tenga su primer flujo real — ahí es donde más se nota la fricción de
clics.

## F2.30 Gestión de ventanas y multitarea *(agregado local)*

⬜ **Sin decidir**, y relacionado con F2.1 (múltiples pestañas/sucursal).
Recuperación de estado al recargar (ej. carrito a medio armar) depende de
F2.8. Diferible hasta que el PDV real exponga el problema concreto.

## F2.31 Microinteracciones y feedback *(agregado local)*

✅ **Resuelto 2026-08-12 (ADR-037)**. Un `loading.tsx` por módulo
(`components/estado/esqueleto-pantalla.tsx`): sin él Next espera a que el
`page.tsx` resuelva y recién ahí pinta, así que el clic en el sidebar no
acusa recibo. La silueta imita la pantalla real —título, acciones, tabla— en
vez de un spinner: un rectángulo donde va a ir la tabla prepara la vista, un
spinner solo informa que hay que esperar.

También: transición de entrada por navegación (`revelar.tsx`), escalonado en
la grilla del home, filas fantasma en la tabla mientras carga, `aria-busy` en
el formulario mientras se envía, y toasts de `sonner` ya montados. Todo el
movimiento cuelga de `--transicion` y se apaga entero con
`prefers-reduced-motion: reduce`.

⬜ **Falta**: indicador de sincronización para el PDV offline (ADR-009), que
depende del motor de sync y no de esta capa.

## Resumen — qué cerrar antes de los diseños finales del alfa

**Actualizado 2026-08-02**: las 6 prioridades originales están resueltas
(layout, componentes base, permisos visuales, arquitectura de carpetas,
estado, tablas). **Primera implementación en código** (no solo spec):
shell Odoo (home de apps + sidebar + `layout.tsx` de guard por módulo,
`frontend/app/(app)/`) y primera pantalla real de un módulo
(`compras/proveedores`: tabla TanStack + alta con `<dialog>` nativo, sin
librería de modal — YAGNI hasta que un formulario complejo la justifique).
El dashboard existente se relocalizó bajo el mismo shell como segunda app.

Sigue en Tailwind + CSS por variables, **sin shadcn/ui todavía**: las
pantallas construidas no necesitaron overlay/combobox/dialog complejo
(el `<dialog>` nativo de alta de proveedor cubrió el caso); shadcn se
instala cuando una pantalla real lo pida, no antes.

El resto de las 31 secciones tiene decisión tomada, está correctamente
diferido, o depende de un módulo backend que todavía no llega a pantalla —
no bloquean seguir construyendo pantallas.
