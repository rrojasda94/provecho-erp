# Logotipos

Los tres del brandbook de Charlie's Pizzas (`D:\Antropic\brand chp\Brandbook_CharliesPizza.pdf`,
p. 28-41), en PNG con fondo transparente:

| Archivo | Tamaño | Dónde se usa |
|---|---|---|
| `logo-horizontal.png` | 545×47 | Cabecera del sitio (`app/layout.tsx`) |
| `logo-vertical.png` | 411×138 | JSON-LD del sitio y la landing del QR del ERP (`frontend/public/marcas/charlies-vertical.png`) |
| `logo-corto.png` (CH'S) | 800×619 | Marca de agua en `/pedido/{id}`; origen de `app/icon.png`, `apple-icon.png`, `favicon.ico` y `opengraph-image.png` |

Reglas del brandbook a respetar: el logo no se condensa, no se separa, no lleva
sombras ni se rota (p. 36); tamaño mínimo legible ≈ 89 px de ancho (cómodo desde
152 px, p. 32). **Sobre fondos oscuros va la versión en negativo, que no tenemos**
(por eso el pie negro solo lleva texto).

## Pendiente
- **SVG** de los tres (sin versión borrosa en pantallas densas): pedirlos a quien
  entregó el brandbook (Dobano). El horizontal mide 47 px de alto: en pantallas
  de alta densidad se ve justo.
- **Versión en negativo** para fondos oscuros.

Para reemplazar un logo: cambiar el archivo conservando el nombre; se referencia por
ruta y ningún componente cambia. Si el reemplazo es SVG, actualizar además la
extensión en `app/layout.tsx`. Los íconos de `app/` se regeneran a partir de
`logo-corto.png` (fondo crema `#F2EBDB`).
