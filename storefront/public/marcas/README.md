# Logotipo

`logo.png` es **provisional** — viene del prototipo portado
(`D:\Anthropic\charlies-pizzas\web\assets\logo.png`), no del brandbook
oficial (`D:\Antropic\brand chp\Brandbook_CharliesPizza.pdf`).

Para poner el definitivo: reemplazar el archivo conservando el nombre. Se
referencia por ruta (`/marcas/logo.png`) desde `app/layout.tsx`; ningún
componente cambia. Preferible un SVG (sin versión borrosa en pantallas
densas) si el brandbook lo entrega en ese formato — cambiar la extensión
implica también actualizar la referencia en `layout.tsx`.
