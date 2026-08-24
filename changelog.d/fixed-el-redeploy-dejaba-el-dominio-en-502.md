- **Desplegar dejaba el dominio público en 502 con la API sana.** Caddy
  resuelve `reverse_proxy api:8000` una sola vez, al arrancar; recrear el
  contenedor `api` le da una IP nueva en la red de Docker y Caddy sigue
  hablándole a la vieja. Pasó desplegando la 0.7.2, y cuesta más
  diagnosticarlo que arreglarlo: `api` figura `Up (healthy)`, `init` termina
  en 0 y el `curl` al loopback responde, así que todo apunta a otro lado. Lo
  único que lo delata es el `CREATED` del `docker compose ps -a` — Caddy con
  horas de vida y `api` con minutos.
- `scripts/desplegar.sh` reinicia Caddy después del `up -d`, así que todo
  despliegue lo cubre, incluido el workflow de ADR-060 — que si no habría
  fallado siempre: su último paso comprueba la versión contra el dominio
  público, justo lo que el 502 rompe. El script tampoco se conforma ya con el
  loopback: espera a `/health/ready` **por el dominio**, que es lo único que
  prueba que el proxy está sirviendo, y si falla ahí dice que mire los logs
  del proxy y no los de la API.
- La solución de fondo —los upstreams dinámicos de Caddy, que re-resuelven el
  DNS— queda en `docs/roadmap/deuda/ci-cd.md` con la configuración escrita: un
  reinicio de proxy por despliegue es un corte de segundos que staging se
  banca y producción no, pero un `Caddyfile` inválido deja staging sin proxy y
  eso hay que validarlo contra el servidor antes de aplicarlo.
