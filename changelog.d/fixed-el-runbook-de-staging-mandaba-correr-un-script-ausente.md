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
- **Y el redeploy dejaba el dominio público en 502 con la API sana.** Caddy
  resuelve `reverse_proxy api:8000` una sola vez, al arrancar; recrear el
  contenedor `api` le da una IP nueva en la red de Docker y Caddy sigue
  hablándole a la vieja. Lo delata el `docker compose ps -a`: Caddy con horas
  de vida y `api` con minutos. El runbook incorpora el
  `docker compose restart caddy` al despliegue y documenta el síntoma, porque
  cuesta más diagnosticarlo que arreglarlo: `api` figura `Up (healthy)` y el
  `curl` al loopback responde, así que todo apunta a que el problema está en
  otro lado. La solución de fondo —los upstreams dinámicos de Caddy, que
  re-resuelven el DNS— queda en deuda con la configuración ya escrita: se
  aplica validando contra el servidor, porque un `Caddyfile` inválido deja
  staging sin proxy y eso es peor que el 502.
