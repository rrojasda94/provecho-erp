- **Guardar un tablero pedía el nombre con `window.prompt`** (2026-08-08).
  El prompt nativo no se puede etiquetar ni estilar, y ningún automatismo de
  navegador lo alcanza: el guardado de un tablero de reportes **no tenía forma
  de probarse de punta a punta**. Ahora el nombre se pide en un diálogo de la
  página, con su `<label>` y su `id`. De paso, guardar sobre un tablero propio
  ya existente dejó de preguntar: conserva su nombre, y solo el alta y
  "Guardar como…" piden uno.
- **Cuatro campos del PDV no tenían nombre accesible** (2026-08-08). El monto
  declarado y el usuario/PIN del encargado en la apertura, y el destino del
  efectivo en el cierre, se apoyaban solo en su `placeholder`: un lector de
  pantalla no anuncia nada y el campo es imposible de alcanzar por nombre. Se
  les agregó `aria-label`.
- **El puerto de la API del suite e2e se puede mover** (2026-08-08). Estaba
  fijo en 8100 en tres archivos (`playwright.config.ts`, `e2e/servidor-api.mjs`
  y `e2e/servidor-web.mjs`) y en una máquina donde ese puerto ya está tomado
  —el `docker-compose` de otro proyecto, sin ir más lejos— la suite entera no
  arranca. `E2E_PUERTO_API` lo mueve sin tocar código; el default no cambia.
- **`TUNNEL_HOST` para probar el dev server desde afuera** (2026-08-08).
  Server Actions rechaza toda request cuyo `Origin` no coincida con el `Host`,
  así que detrás de un túnel público —probar el PDV en un celular real, por
  ejemplo— el login moría con `Invalid Server Actions request`. La variable es
  inerte si no está definida: nunca se activa en producción.
