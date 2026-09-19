# Tipografía

**Tusker Grotesk**, la principal del brandbook (p. 47-49). Solo los dos cortes que
usa el sitio, en WOFF2:

| Archivo | Corte | Uso |
|---|---|---|
| `TuskerGrotesk-4500Medium.woff2` | 4500 Medium | Texto (peso 400-500) |
| `TuskerGrotesk-5800Super.woff2` | 5800 Super | Énfasis y títulos (peso 600-900) |

Se cargan con `next/font/local` en `app/layout.tsx` (variable `--fuente-tusker`).

## Pendiente
- **Isidora Black** (7800), la fuente de titulares del brandbook, no vino en el
  paquete. Cuando llegue: agregarla acá, declararla en `app/layout.tsx` y apuntar
  `--fuente-display` (`app/globals.css`) a ella.

**Licencia:** Tusker Grotesk es de uso libre (confirmado por la marca, 2026-09-19); se puede servir en el sitio.
