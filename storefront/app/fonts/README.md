# Tipografía

Tres papeles, tres fuentes. Se cargan con `next/font/local` en `app/layout.tsx`
y se eligen por variable en `app/globals.css`.

| Papel | Variable | Fuente | Dónde |
|---|---|---|---|
| Cuerpo de texto | `--fuente-cuerpo` | la sans del sistema (`system-ui`…) | párrafos, formularios, listas |
| Títulos y rótulos | `--fuente-display` | `TuskerGrotesk-5800Super.woff2` | `.font-display`: subtítulos, precios, botones |
| Título de página | `--fuente-titular` | `isidora-black.woff2` | `.font-titular`: el `h1` grande de cada página |

`TuskerGrotesk-4500Medium.woff2` (peso 400-500) sigue declarada: es el corte que
usa cualquier texto que herede `--fuente-tusker`.

## Por qué el cuerpo no usa Tusker

El brandbook (p. 48) dice que Tusker sirve "para encabezados y cuerpos de
texto". En un impreso sí; en pantalla no. Es una grotesca **condensada**, y
leer párrafos seguidos en ella cansa — el reporte textual, después de usar el
sitio: *"es un poco tedioso leer oraciones con Tusker"* (2026-09-20). Se queda
donde luce, que es en títulos, precios y botones.

La sans del sistema, además de ser la que mejor se lee en cada dispositivo, no
pesa nada ni parpadea al cargar.

## Por qué Isidora solo va en el `h1`

Del paquete de Isidora llegó **únicamente el corte Black (900)**. Es el peso
que el brandbook le asigna (Isidora Black 7800, p. 49) y funciona para un
titular grande; un párrafo entero en negra 900 cansaría más que la condensada
que se quiso evitar. Si algún día llega la familia completa (Regular, Medium),
el cuerpo puede pasar a Isidora cambiando una línea: `--fuente-cuerpo`.

## Licencias

- **Tusker Grotesk**: de uso libre, confirmado por la marca (2026-09-19).
- **Isidora Black**: el archivo llegó de un agregador de fuentes gratuitas, no
  de la fundición. Isidora es una familia comercial de Latinotype: antes de que
  el sitio salga de staging conviene confirmar con quien entregó el brandbook
  que la marca tiene licencia web, o comprarla.
