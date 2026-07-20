# Contexto para trabajar en frontend

Leer antes: `/CLAUDE.md` y [product/ui-ux.md](../product/ui-ux.md).

## Reglas duras

- Colores y fuentes SOLO vía tokens CSS de `frontend/app/globals.css` —
  nunca hex hardcodeado (el PDV re-tematiza por marca cambiando variables).
- Anton Italic para titulares (h1–h4 ya lo heredan), Inter para texto.
- Responsive siempre (webapp + Android 15+).
- TypeScript estricto; componentes en PascalCase; App Router de Next.js.
- Datos solo de la API REST (`NEXT_PUBLIC_API_URL`) — sin lógica de negocio en el front.

## Checklist

- [ ] `npm run lint` y `npm run build` limpios.
- [ ] Probado en viewport móvil y desktop.
- [ ] Sin colores/tamaños mágicos fuera de tokens.
