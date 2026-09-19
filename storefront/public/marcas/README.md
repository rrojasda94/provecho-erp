# Logotipos

Los tres logotipos oficiales de Charlie's Pizzas en **SVG** (entregados por la marca,
carpeta `Logotipo/` de su Drive: `CH1-H`, `CH1-V`, `CH1-R`). Un solo color, el verde
de marca `rgb(0,169,24)`, sin fondo.

| Archivo | Proporción | Dónde se usa |
|---|---|---|
| `logo-horizontal.svg` | 2265×192 | Cabecera del sitio (`app/layout.tsx`) |
| `logo-vertical.svg` | 1711×570 | Origen de `logo-vertical.png` y de la landing del QR del ERP (`frontend/public/marcas/charlies-vertical.svg`) |
| `logo-corto.svg` (CH'S) | 1617×1251 | Marca de agua en `/pedido/{id}`; origen de `app/icon.png`, `apple-icon.png` y las imágenes para compartir el enlace |
| `logo-vertical.png` | 1200×400 | Derivado del SVG: solo para el JSON-LD (`app/layout.tsx`), que pide un raster |

`app/favicon.ico` no se regenera (no hay herramienta de `.ico` en el repo): sigue siendo el
de la ronda anterior.

Reglas del brandbook a respetar: el logo no se condensa, no se separa, no lleva
sombras ni se rota (p. 36); tamaño mínimo legible ≈ 89 px de ancho (cómodo desde
152 px, p. 32). **Sobre fondos oscuros va la versión en negativo, que no tenemos**
(por eso el pie negro solo lleva texto).

## Pendiente
- **Versión en negativo** para fondos oscuros.

Para reemplazar un logo: cambiar el archivo conservando el nombre; se referencia por
ruta y ningún componente cambia. Los íconos de `app/` y `logo-vertical.png` se derivan
del SVG con `sharp` (ícono 512, apple 180, compartir 1200×630, todos sobre crema
`#F2EBDB`).
