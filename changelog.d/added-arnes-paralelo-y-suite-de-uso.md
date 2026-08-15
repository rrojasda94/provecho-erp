- **Dos agentes ya pueden correr Playwright a la vez** (2026-08-15). El
  puerto web estaba fijo en `3100` dentro del código —`E2E_PUERTO_API` existía,
  su par no— así que la segunda suite que arrancaba chocaba con la primera o,
  peor, reusaba su servidor y corría contra código de otro worktree **en
  verde**. Ahora hay `E2E_PUERTO_WEB` y un esquema de slots (`810N` / `310N` /
  `provecho_slotN`) en `docs/engineering/trabajo-en-paralelo.md`.
- **El intérprete de Python se resuelve solo** (2026-08-15). Los scripts de
  la suite usaban `process.env.PYTHON ?? "python"`, y en un worktree no hay
  `.venv` —vive una sola vez en la raíz del repo principal—: el `python` del
  PATH no tiene instalado el paquete `src` y la corrida moría con
  `ModuleNotFoundError` tres pasos antes de la prueba que alguien quería
  correr. `frontend/e2e/interprete.mjs` busca el `.venv` del worktree, después
  el del repo principal (vía `git rev-parse --git-common-dir`) y recién
  entonces cae a `python`. `PYTHON` sigue mandando sobre todo.
- **Suite de uso separada de la de e2e** (2026-08-15, ADR-047).
  `npm run test:uso` corre `frontend/uso/` con captura en cada hito, traza
  siempre y sin reintentos, y su job de CI **no es requerido**: el techo de
  tres casos de `e2e` sigue vigente porque bloquea todo merge, y un recorrido
  lento no puede frenar un arreglo de caja. El arranque de los dos servidores
  quedó en `frontend/playwright.comun.ts`, que las dos configs comparten en
  vez de copiarse. Esta entrega deja **una sola spec de humo**: prueba el
  arnés, no una pantalla.
- **El seeder de e2e siembra lo que las ramas iban a sembrar de a una**
  (2026-08-15). `src/seeders/e2e.py` agrega `Menú E2E` —producto con
  variantes, grupo de opciones obligatorio y extras, el modelo de nodos
  completo—, cuatro insumos con stock real en el almacén central, un
  proveedor y una orden de compra en borrador. Sigue siendo idempotente y
  prohibido en producción. `Pizza E2E` no se tocó a propósito: es plana
  porque las pruebas del lienzo dependen de que tenga un único insumo.
- **Conteos de pruebas al día en la estrategia** (2026-08-15). Decía 895
  casos de backend, 183 de frontend y 7 de e2e; los reales son **1379**
  (1041 funciones `test_*` en 76 archivos, la diferencia son `parametrize`),
  **258** y **13**. Un conteo escrito a mano envejece sin avisar, y estos
  llevaban nueve días vencidos.
