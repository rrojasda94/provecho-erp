- **`/health`, `/health/ready` y `/health/backups` rechazaban `HEAD` con 405**
  (encontrado 2026-08-23 al dar de alta el monitor externo de staging en
  UptimeRobot, plan gratis, que sondea con `HEAD` y no permite cambiar a
  `GET`). Causa: la versión instalada de FastAPI dejó de agregar `HEAD`
  automático a las rutas `GET`. Los tres endpoints ahora registran `HEAD`
  explícito, fuera del contrato OpenAPI (es implícito en HTTP, no hace
  falta documentarlo aparte).
