# ADR-060 — Desplegar desde GitHub, a pedido

- Estado: aceptado
- Fecha: 2026-08-23
- Contexto: entrega y despliegue
- Relacionado: ADR-008 (entrega continua), `docs/engineering/staging.md`

## Contexto

ADR-008 separó **entrega** de **despliegue** y automatizó solo la primera:
cada push a `main` publica una imagen en GHCR, y el despliegue quedó "manual y
documentado **hasta que exista el VPS**".

El VPS existe desde hace días. Y lo que quedó no es un despliegue manual: es
un despliegue **atado a una máquina**. Para correr `./scripts/desplegar.sh`
hace falta esa PC, con esa llave, y la llave tiene passphrase — así que
tampoco sirve desde un shell no interactivo.

El 2026-08-23 eso dejó staging sin actualizar con 0.7.1 ya publicada, porque
quien tenía que desplegar estaba en otra ubicación. Un despliegue que depende
de dónde está parada una persona no es un proceso, es una casualidad.

## Decisión

Un workflow `Desplegar` con **`workflow_dispatch`**: se elige la versión y se
le da a Run desde la web de GitHub.

### Por qué a pedido y no automático

`workflow_dispatch` y no `on: push` ni `on: tag`. Lo que ADR-008 protegía era
que **el despliegue fuera un acto explícito**, y eso sigue en pie: alguien
elige qué versión y decide cuándo. Lo que cambia es que ese alguien puede
estar en cualquier parte, con un teléfono.

Automatizarlo por tag se evaluó y se descartó: etiquetar una versión y tocar
el servidor son dos decisiones distintas, y juntarlas quita la ventana para
mirar el CHANGELOG antes de que la versión esté arriba.

### El script viaja del repo al servidor en cada despliegue

`scp scripts/desplegar.sh` antes de correrlo, en vez de asumir que en el
servidor hay una copia. Una copia vieja allá es un despliegue que hace algo
distinto de lo que dice el repo, y nadie se entera hasta que falla — que es
exactamente la clase de desfase que ya costó dos arreglos esta semana
(el contrato desactualizado y la imagen sin `scripts/odoo`).

### La huella del servidor va en un secreto

`StrictHostKeyChecking` se resuelve con `STAGING_KNOWN_HOSTS`, no con
`=no`. Con `=no`, cualquiera que se meta en el medio se lleva una sesión con
permiso de desplegar. Es dos minutos de `ssh-keyscan` una sola vez.

### Se comprueba desde afuera

El último paso pide `openapi.json` **al dominio público** y muestra la versión
en el resumen del workflow. Que el contenedor arranque no significa que el
proxy lo esté sirviendo, y `desplegar.sh` solo mira `127.0.0.1` desde adentro.

### La carga del catálogo, solo en simulación

El workflow puede correr `cargar_catalogo --simular`, que deshace todo al
final y no escribe nada. La carga de verdad **no** se automatiza: escribe
cientos de filas de negocio y se hace mirando primero el resultado de la
simulación.

## Alternativas descartadas

- **Runner propio en el droplet.** Evita guardar en GitHub una llave que
  llega al servidor, y a cambio deja un proceso con acceso al repositorio
  corriendo *en* el servidor, más una pieza que actualizar. Para un droplet y
  un entorno, la cuenta no cierra.
- **Watchtower o similar**, que el servidor mire GHCR y actualice solo. No
  hay credencial en GitHub, y se pierde el acto explícito y el orden de la
  migración: `alembic upgrade head` tiene que correr **antes** de que arranque
  la API, y eso lo resuelve el servicio `init` del compose, no un vigilante de
  imágenes.
- **Desplegar desde el CI al mergear.** Ver arriba: son dos decisiones.
- **Guardar la passphrase de la llave personal como secreto.** La llave de
  despliegue tiene que ser **propia y sin passphrase**, no la de una persona:
  así se puede revocar sin dejar a nadie sin acceso, y su alcance es el que
  se le dé en `authorized_keys`.

## Consecuencias

- Dos secretos nuevos en el repositorio: `STAGING_SSH_KEY` (llave privada de
  despliegue, dedicada y sin passphrase) y `STAGING_KNOWN_HOSTS`. Cómo
  crearlos está en `docs/engineering/devops.md`.
- Tres variables opcionales (`STAGING_HOST`, `STAGING_USER`, `STAGING_DIR`)
  con el valor actual por defecto: recrear el droplet cambia la IP y no
  debería obligar a tocar el workflow.
- El job usa el `environment: staging` de GitHub. Vacío no estorba, y es
  donde se le agregan revisores obligatorios el día que haga falta aprobar
  antes de tocar el servidor.
- `concurrency` con `cancel-in-progress: false`: dos despliegues a la vez se
  pisan el `up -d` y dejan el servidor en un estado que no es ninguna de las
  dos versiones. El segundo espera.
- La llave se borra del runner en `always()`. Es higiene, no seguridad — el
  runner es efímero —, pero un `if: failure()` a medias es cómo queda un
  archivo con una llave en un paso que alguien agregue después.
- Producción **no** entra en este ADR. Cuando exista, el mismo workflow puede
  ganar un `entorno` de entrada, con su propio environment y sus revisores.
