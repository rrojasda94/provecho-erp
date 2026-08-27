- **La landing pública del QR tiene dominio propio**
  (`clientes.majambo.com.pe`, ADR-072). El QR de la mesa apuntaba a
  `staging.majambo.com.pe/reconocerte`: un nombre que anuncia que es un
  entorno de prueba y cuya raíz es el ERP entero. El recorte va en el
  `Caddyfile` y no en el código —el `matcher` de `middleware.ts` excluye los
  prefetch, así que un guard ahí lo saltearía cualquiera mandando
  `Next-Router-Prefetch: 1` a mano—: por ese dominio solo pasan
  `/reconocerte*`, `/_next/static/*`, `/_next/image*`, `/marcas/*` y el
  favicon; todo lo demás redirige 302 a la landing, y va con
  `X-Robots-Tag: noindex`. Dos costos aceptados y escritos: los chunks de
  `/_next/static` son los mismos para las dos caras, así que por ahí se ven
  las rutas del back office (estructura, no datos); y **no es un control de
  seguridad** — `/login` sigue igual de público en el otro dominio y lo que lo
  protege es el login. Lo que se registre ahí cae en la base desechable de
  staging: es una prueba, no el padrón de clientes.
