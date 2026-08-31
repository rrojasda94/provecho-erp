- **El token de autorización de supervisor se podía reusar durante sus tres
  minutos** (2026-08-30, hallazgo #7 de la auditoría backend↔frontend;
  ADR-018 §6). `POST /auth/autorizar` emitía un `jti` desde el primer día y
  `verificar()` nunca lo miraba: el cajero conseguía la firma legítima del
  supervisor para un descuento y se la aplicaba a las ventas siguientes, con
  el reporte de descuentos —la razón de ser del campo— nombrando al
  supervisor en todas. Ahora la elevación cubre **una** operación: el `jti`
  se consume al verificarlo, con la marca en Redis (`marcar_uso_unico` en
  `src/core/rate_limit.py`, `SET NX EX` con el TTL de la elevación, sobre el
  mismo cliente y corta-circuito del rate limit). La marca guarda la clave
  de idempotencia de la operación cuando la hay, para que un reintento de
  red no obligue al supervisor a volver al mostrador. Costo aceptado: la
  guarda es fail-open como el rate limit, así que con Redis caído no hay
  anti-replay — el token sigue acotado a 3 minutos y a un permiso. Llevar la
  marca a Postgres cerraría eso y pide tabla y purga; queda en la deuda.
