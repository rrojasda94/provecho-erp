- **Cuentas de cliente en el sitio de Charlie's Pizzas, PR2** (2026-09-17,
  ADR-104). Registro e ingreso con email/clave o con Google, direcciones
  guardadas (con predeterminada), favoritos y "tu último pedido" en la
  cuenta y en el home. La cuenta web (`storefront_cuenta`) es una
  credencial **separada** de la del ERP: JWT propio
  (`STOREFRONT_JWT_SECRET`, `aud="storefront"`), nunca intercambiable con
  el del staff — un token de una cuenta web devuelve 401 en cualquier
  endpoint del ERP, y viceversa.

- **Vínculo automático a `cliente` por evento.** Al registrarse (email o
  Google), `storefront` publica `storefront.cuenta_registrada`; un
  listener de `sales` crea o encuentra el `cliente` correspondiente
  (RENIEC + fallback, idempotente por documento) y publica
  `sales.cliente_vinculado`, que `storefront` usa para completar
  `cuenta.cliente_id`. Si faltan datos para crear el cliente, la cuenta
  queda sin vincular sin romper el registro.

- **Seguridad de la cuenta**: Argon2id, bloqueo tras 5 intentos fallidos
  (15 minutos), rotación de refresh token con detección de reuso — si un
  refresh token ya usado vuelve a presentarse, se revoca toda la cadena
  de sesión, no solo el token robado.
