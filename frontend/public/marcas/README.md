# Logotipos

**Los dos SVG de esta carpeta son provisionales.** Están armados con
tipografía y los colores de marca de `app/globals.css` (brasa `#c6390f`,
tinta `currentColor`), no con los originales.

Para poner los definitivos: **reemplazar el archivo, conservando el nombre**.
Nada más — la landing los referencia por ruta (`/marcas/majambo.svg`,
`/marcas/charlies.svg`) y ningún componente cambia.

| Archivo | Dónde se usa | Qué debe traer |
|---|---|---|
| `majambo.svg` | pie de la landing pública | logotipo del **grupo** |
| `charlies.svg` | cabecera de la landing pública | logotipo de la **marca** |

Recomendaciones para los definitivos:

- **SVG**, no PNG: la landing se abre casi siempre en un teléfono y el SVG no
  tiene versión borrosa en pantallas densas.
- `viewBox` puesto y **sin `width`/`height` fijos**: el CSS los dimensiona.
- El color que deba seguir al tema va como `currentColor`; el que sea del
  logotipo, en su hex.
- Con `<title>` adentro: es lo que lee un lector de pantalla.

La CSP (`frontend/middleware.ts`) ya permite `img-src 'self'`, así que un
archivo servido desde acá carga sin tocar nada. Un logotipo alojado en otro
dominio **no** cargaría, y abrir la CSP a un host nuevo es decisión de ADR.
