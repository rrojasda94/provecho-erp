- **Provecho como proveedor OAuth2 para el SSO del BI** (ADR-083, Fase B;
  RN-BI-004/005/006). Sin tabla nueva: `src/core/oauth/` guarda el código de
  autorización y el access token en Redis, con TTL corto y un solo uso
  (`GETDEL`) — ninguno de los dos se pensó para durar una sesión, solo lo
  que tarda el navegador en rebotar de vuelta a Superset. Falla **cerrado**:
  a diferencia de `core/rate_limit.py`, un Redis caído corta el SSO en vez
  de dejarlo pasar.
- **El hallazgo que decidió dónde vive cada pieza**: la sesión de Provecho
  (`provecho_token`) es una cookie httpOnly y host-only de
  `staging.majambo.com.pe`, y la API vive en `api-staging.majambo.com.pe` —
  un subdominio al que esa cookie nunca llega. Un `/oauth/authorize` de
  FastAPI no podría leerla. Por eso el paso que ve el navegador
  (`GET /oauth/authorize`) es un Route Handler del **frontend**
  (`frontend/app/oauth/authorize/route.ts`): lee la sesión ahí, donde sí
  existe, y llama a `POST /api/v1/oauth/codigo` (JWT + `bi.acceder`) ya
  autenticado. `/oauth/token` y `/oauth/userinfo` son servidor-a-servidor,
  los llama Superset con `client_secret` o el token que acaba de recibir —
  nunca el navegador.
- **`redirect_uri` se valida por igualdad exacta, nunca por prefijo**
  (RN-BI-005): el frontend jamás construye una redirección hacia un destino
  que la API no haya aprobado antes, que es lo que evita usar este flujo
  como open redirect.
- **El login gana un `?next=` de un único destino posible**: si el SSO
  encuentra a alguien sin sesión de Provecho todavía, lo manda a `/login`
  y, tras autenticarse, de vuelta exacta a `/oauth/authorize` — antes
  siempre volvía al home. Whitelisteado por regex a ese único caso; nada
  más puede pedir un destino post-login distinto.
- **Permiso `bi.acceder` adelantado desde la Fase D**: `POST /oauth/codigo`
  no tiene sentido sin él, así que se seedea ahora en `admin` (vía `*`),
  `supervisor` y `contador`. Lo que sigue en Fase D es la navegación
  (entrada del BI en el home), no el permiso.
