- **Staging se despliega desde GitHub** (ADR-060). Actions → *Desplegar* → Run
  workflow, se elige la versión y listo. Se puede desde un teléfono.

  ADR-008 había dejado el despliegue manual "hasta que exista el VPS". El VPS
  existe, y lo que quedó no era un despliegue manual sino uno **atado a una
  máquina**: hace falta esa PC, con esa llave, y la llave tiene passphrase —
  así que tampoco sirve desde un shell no interactivo. Eso dejó staging sin
  actualizar con 0.7.1 ya publicada, porque quien tenía que desplegar estaba
  en otra ubicación.

  Sigue siendo un **acto explícito** (`workflow_dispatch`, no `on: push`), que
  es lo que ADR-008 protegía. Lo que cambia es que ese alguien puede estar en
  cualquier parte.

  - El script de despliegue **viaja del repo al servidor** en cada corrida, en
    vez de asumir que allá hay una copia: una copia vieja es un despliegue que
    hace algo distinto de lo que dice el repo.
  - La huella del servidor va en un secreto, no `StrictHostKeyChecking=no`.
  - Se comprueba la versión **desde afuera**, contra el dominio público: que
    el contenedor arranque no significa que el proxy lo esté sirviendo.
  - La carga del catálogo solo se ofrece **en simulación**, que no escribe
    nada. La de verdad se hace a mano mirando ese resultado.

  Requiere dos secretos, documentados en `docs/engineering/devops.md`.
