- **La raíz de cinco módulos daba 404** (2026-08-15). `catalogo`, `compras`,
  `inventario`, `organizacion` y `rrhh` tenían carpeta, `layout.tsx` y todas
  sus pantallas, pero ninguna ruta en la raíz: el ícono del home apunta a la
  primera pantalla (`/catalogo/productos`), así que nada del shell enlazaba
  `/catalogo` y el agujero no se veía. Sí lo teclea quien recorta la URL para
  subir un nivel, que es justo lo que uno hace cuando se perdió. Ahora cada
  raíz redirige a `modulo.href` leído de `lib/modulos.ts`: la primera pantalla
  de un módulo cambia, y dos lugares donde declararla son dos lugares donde
  puede quedar mal.
- **El ERP no tenía pantalla de 404**: cualquier dirección equivocada caía en
  la página por defecto de Next —fondo blanco, "404" en inglés y ninguna
  salida—. En una tablet detrás de la barra, una pantalla sin botón de vuelta
  se resuelve apagando y volviendo a entrar. `app/not-found.tsx` dice qué pasó
  en español y ofrece el inicio. No repite la ruta que falló: quien tecleó la
  dirección ya la vio, lo que le falta es la puerta.
- **Nada ataba la navegación al árbol de archivos**: `lib/navegacion.test.ts`
  cruza `MODULOS` con `SUBMENUS`, pero los dos pueden estar de acuerdo
  apuntando a una pantalla que no existe. Por eso la deuda "7 íconos del home
  llevan a 404" sobrevivió meses después de que esas pantallas se
  construyeran, sin que nadie pudiera decir si seguía siendo cierta.
  `lib/rutas.test.ts` resuelve los 14 íconos y los 25 ítems de submenú contra
  los `page.tsx` reales, y comprueba que ninguna raíz se redirija a sí misma.
