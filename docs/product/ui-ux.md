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

- Menús, buscadores, breadcrumbs, atajos de teclado, sidebars, dashboards y
  diseño visual de pantallas.
- Catálogo exacto de paletas de accesibilidad y niveles de tamaño de fuente.
- Si Grupo Majambo tiene tema propio distinto al de Provecho, o si Provecho
  es el tema por defecto también para Grupo Majambo.
