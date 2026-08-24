- **El runbook de staging mandaba correr un script que no está en el
  servidor.** `docs/engineering/staging.md` indicaba
  `./scripts/desplegar.sh <version>`, pero el repo nunca se clonó en el
  droplet —solo se copiaron a mano `docker-compose.staging.yml` y el
  `Caddyfile`—, así que desplegar la 0.7.2 falló con `No such file or
  directory`. Mismo patrón que el arreglo de la 0.7.1 con `scripts/odoo`: el
  README manda correr algo que no está donde dice. El runbook ahora lleva el
  `docker compose up -d --pull always` equivalente y la verificación de
  `/health/ready`, y cerrar el hueco de raíz quedó anotado en
  `docs/roadmap/deuda/ci-cd.md` junto al job de despliegue, que lo resuelve.
