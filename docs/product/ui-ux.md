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
  ERP.
- **Grupo Majambo** puede tener su propio tema corporativo para los módulos
  de back-office (paleta/tipografía propias, distintas de Provecho) —
  pendiente definir con el negocio si sustituye o convive con Provecho.
- **PDV y Kiosk son las pantallas con MÁS variación de skin**: son el "front"
  de cada marca del grupo (Charlie's, Ariana, La Avenida, ...) y cada una
  puede sobreescribir su propio tema completo (paleta, tipografía, logo),
  configurable por marca/sucursal en el módulo de ajustes.
- El resto de módulos (inventario, KDS, compras, contabilidad, comercial,
  RRHH, gerencia, marketing) usan el tema de Provecho o de Grupo Majambo —
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
- Pendiente definir con el negocio: catálogo exacto de paletas alternativas
  y cuántos niveles de tamaño de fuente.

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

## Pendiente de definición (con el negocio)

- Menús, buscadores, atajos de teclado, dashboards y diseño visual de
  pantallas. **Mecanismo de navegación ya decidido** (ADR-013: home de apps
  + sidebar por módulo estilo Odoo) — pendiente es el contenido de cada
  menú, no la estructura.
- Catálogo exacto de paletas de accesibilidad y niveles de tamaño de fuente.
- Si Grupo Majambo tiene tema propio distinto al de Provecho, o si Provecho
  es el tema por defecto también para Grupo Majambo.
