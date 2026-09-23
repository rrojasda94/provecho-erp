# Logotipos

Los tres logotipos oficiales de Charlie's Pizzas en **SVG** (entregados por la marca,
carpeta `Logotipo/` de su Drive: `CH1-H`, `CH1-V`, `CH1-R`), en **tres tintas** según el
fondo. Es el mismo trazado; solo cambia el relleno:

| Sufijo | Color | Cuándo |
|---|---|---|
| *(ninguno)* | aceituna negra `#505b52` (`--chp-tinta`; brandbook p. 52: CMYK 53 47 52 33) | **fondo claro** (crema, blanco). Es el que referencian las páginas |
| `-crema` | crema `#f2ebdb` | **fondo oscuro** (el pie negro) |
| `-verde` | verde de marca `rgb(0,169,24)` | el original tal cual lo entregó la marca; fuente de los íconos y de `logo-vertical.png` |

| Logo | Proporción | Dónde se usa |
|---|---|---|
| `logo-horizontal*.svg` | 2265×192 | Cabecera (aceituna) y pie (crema) de `app/layout.tsx` |
| `logo-vertical*.svg` | 1711×570 | Landing del QR del ERP (`frontend/public/marcas/charlies-vertical.svg`, aceituna) y ticket térmico (`frontend/public/marcas/charlies.svg`, negro puro) |
| `logo-corto*.svg` (CH'S) | 1617×1251 | Marca de agua de `/pedido/{id}` (aceituna); `-verde` es el origen de `app/icon.png`, `apple-icon.png` y las imágenes para compartir |
| `logo-vertical.png` | 1200×400 | Derivado de `-verde`: solo el JSON-LD (`app/layout.tsx`), que pide un raster |

Un logo en `<img>` no hereda `currentColor`, por eso son archivos distintos y no un solo SVG.
Para otro fondo (rojo, foto) hace falta otra variante: copiar el archivo y cambiar el relleno.

`app/favicon.ico` no se regenera (no hay herramienta de `.ico` en el repo): sigue siendo el
de la ronda anterior.

Reglas del brandbook a respetar: el logo no se condensa, no se separa, no lleva
sombras ni se rota (p. 36); tamaño mínimo legible ≈ 89 px de ancho (cómodo desde
152 px, p. 32). Sobre fondos oscuros va la versión crema (`-crema`).

Para reemplazar un logo: cambiar el archivo conservando el nombre; se referencia por
ruta y ningún componente cambia. Los íconos de `app/` y `logo-vertical.png` se derivan
del SVG `-verde` con `sharp` (ícono 512, apple 180, compartir 1200×630, todos sobre crema
`#F2EBDB`).
