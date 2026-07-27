# Contexto para trabajar en frontend

Leer antes: `/CLAUDE.md` y [product/ui-ux.md](../product/ui-ux.md).

## Reglas duras

- Colores y fuentes SOLO vía tokens CSS de `frontend/app/globals.css` —
  nunca hex hardcodeado (PDV/Kiosk re-tematizan por marca cambiando
  variables; el resto de módulos usa Provecho/Grupo Majambo).
- Anton Italic para titulares (h1–h4 ya lo heredan), Inter para texto.
- Responsive siempre (webapp + Android 15+); táctil obligatorio en
  PDV/Kiosk/KDS/Inventario, el resto de módulos es PC-first pero igual
  responsive.
- Accesibilidad: paleta alternativa (daltonismo) y tamaño de fuente
  ajustable, ambos como preferencia del perfil del usuario, combinables
  con el tema de marca activo.
- TypeScript estricto; componentes en PascalCase; App Router de Next.js.
- Datos solo de la API REST (`NEXT_PUBLIC_API_URL`) — sin lógica de negocio en el front.

## Checklist

- [ ] `npm run lint` y `npm run build` limpios.
- [ ] Probado en viewport móvil y desktop.
- [ ] Sin colores/tamaños mágicos fuera de tokens.
