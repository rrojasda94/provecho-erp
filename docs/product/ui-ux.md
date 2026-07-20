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

## Reglas de implementación

- Colores y fuentes SOLO vía tokens CSS (`frontend/app/globals.css`).
  Nunca hex hardcodeado en componentes.
- Branding Provecho en TODO el ERP; el **PDV** sobreescribe los tokens con el
  branding de cada marca (configurable en el módulo de ajustes).
- Responsive en todas las pantallas (webapp + Android 15+).

## Pendiente de definición (con el negocio)

Menús, buscadores, breadcrumbs, atajos de teclado, sidebars, dashboards y
diseño visual de pantallas.
