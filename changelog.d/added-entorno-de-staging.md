- **Entorno de staging** (2026-08-23): droplet en DigitalOcean, dominio y
  TLS automático (Caddy). Nuevo `docker-compose.staging.yml`, `Caddyfile`,
  `.env.staging.example`, `scripts/desplegar.sh` y `docs/engineering/staging.md`
  con la bitácora del servidor (sin secretos).
- **`release.yml` publica también la imagen del frontend** — hasta ahora
  solo empaquetaba el backend en GHCR; sin la imagen web, staging (y
  cualquier despliegue futuro) no tenía pantallas.
