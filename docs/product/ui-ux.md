# UI / UX y branding

## Branding Provecho (brandboard 2026-07)

### Paleta

| Token CSS | Hex | Uso |
|-----------|-----|-----|
| `--color-primary` | `#F4511E` | Naranja fuego — acciones primarias, logo |
| `--color-secondary` | `#B71C1C` | Rojo — alertas/énfasis |
| `--color-dark` | `#161616` | Negro — fondos oscuros, texto sobre claro |
| `--color-cream` | `#FFF1DC` | Crema — fondo claro por defecto |
| `--color-accent` | `#AEEA00` | Verde lima — acentos, éxito |
| `--color-gray` | `#757575` | Gris — texto secundario, bordes |

### Tipografías

- **Anton Italic** — titulares y logotipo (mayúsculas, cursiva). Google Fonts
  `Anton` + `font-style: italic` (la fuente no trae itálica nativa).
- **Inter** — textos y cuerpo (Regular / Medium / Bold).

### Identidad

- Logotipo: "P" en llamas + PROVECHO (Anton Italic). Variantes: horizontal,
  vertical (tagline "Hub Gastronómico"), isotipo reducido, monocromática,
  verde lima sobre oscuro.
- Frase de campaña: **"¿Qué se te antoja hoy?"**
- Estilo gráfico: texturas urbanas (concreto, grunge, spray).

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

### Catálogo de paletas y tamaños de fuente (propuesta técnica, 2026-07-27)

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
| `--status-success` | `--color-accent` `#AEEA00` (verde lima) | `#0072B2` (azul) |
| `--status-danger` | `--color-secondary` `#B71C1C` (rojo) | `#D55E00` (naranja vermellón) |
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

Ambas preferencias viven en `usuario` (ej.
`preferencia_paleta: estandar\|alto_contraste`,
`preferencia_tamano_fuente: estandar\|grande\|muy_grande\|maximo`) — sin
implementar todavía, ver `docs/product/frontend-architecture.md` F2.14.

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
  editar, activar/desactivar; filtro por categorías) con `kds.configurar`.
  Van juntas a propósito — es la misma lista, y quien configura una estación
  lo hace mirando el tablero que la cocina usa. Desactivar es baja lógica:
  la pantalla deja de aparecer en cocina, no se borra.

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
