# Deuda técnica — Seguridad (tras el endurecimiento base de 2026-07-26)

Parte del backlog de deuda técnica del proyecto. El índice y las reglas
de uso están en [`ROADMAP.md`](../../../ROADMAP.md) → Deuda técnica.

- ⬜ **El hub de sucursal sigue autenticándose con username + PIN**
  (`cloud_sync_username` / `cloud_sync_pin`), aunque desde 2026-08-08 existe
  la credencial correcta para una cuenta de servicio (`token_agente`,
  ADR-032). Migrarlo no es cambiar código: hay que emitir un token por
  local, rotar el `.env` de cada hub y desplegarlos — un cambio de
  operación, no de aplicación. Hasta que se haga, el secreto de sync sigue
  teniendo 20 bits y el lockout de 5 intentos puede dejar una sucursal sin
  sincronizar.
- ✅ 2026-08-12 **Reseteo de PIN** (ADR-041): un PIN olvidado no se
  recuperaba y el frontend documentaba un endpoint de autoservicio que no
  existía. Permiso propio `users.resetear_pin`, marca en la cuenta que la
  bloquea hasta cambiarlo, revocación de sesiones y auditoría.
- ⬜ **La consulta de DNI/RUC no tiene rate limit propio** (2026-08-12,
  ADR-041). `GET /consulta/{dni,ruc}/{n}` gasta cuota de un proveedor **pago**
  y hoy solo `/auth/login` está detrás de un límite. Con el permiso acotado a
  cuatro roles el riesgo es de costo y no de fuga, pero una pantalla con un
  bucle mal escrito basta para agotar el plan del mes. Va con el rate limit
  global (más abajo) o con uno propio, lo que llegue primero.
- ⬜ **Dar de baja un almacén no mira el stock** (2026-08-08, con el CRUD de
  organización): `DELETE /almacenes/{id}` niega la baja si otros almacenes
  se abastecen de este, pero el stock vive en `inventory` y `users` no
  importa el dominio de otro módulo (CLAUDE.md). Cuando el caso sea real, va
  por evento o por contrato público de `inventory` — nunca por import.
- ⬜ **El seeder no revoca** (encontrado 2026-08-05 al retirarle
  `purchases.aprobar` al rol `supervisor`): `ROLES` solo agrega los permisos
  que faltan, así que sacar uno del mapa no lo quita de ninguna base ya
  sembrada. Un permiso retirado por decisión de negocio sigue vigente en
  producción hasta que alguien lo borra a mano —que es lo que hubo que
  hacer acá—. Sincronizar en los dos sentidos es fácil; lo que hay que
  pensar antes es qué pasa con los permisos que un admin asignó a mano y no
  están en el mapa, porque una sincronización ingenua se los lleva puestos.
- ⬜ **Rate limit global**, no solo en auth: el resto de la API sigue sin
  límite. Se resuelve mejor en nginx/Caddy (`limit_req`) que en la
  aplicación — decidir al configurar el servidor de producción.
- ⬜ **Ventana deslizante en el rate limit**: hoy es ventana fija; un pico
  justo en el borde deja pasar hasta el doble del límite. Solo vale la pena
  si aparece abuso real.
- ⬜ **Rate limit por usuario además de por IP**: una IP compartida (la
  sucursal entera sale por la misma) puede agotar el límite de todos.
  Evaluar cuando haya varias cajas por local.
- ✅ 2026-08-04 **Content-Security-Policy**, en las dos puntas y con
  criterios distintos porque son dos cosas distintas:
  **API** (`src/core/app.py`) devuelve JSON y no tiene por qué cargar nada,
  así que va la más restrictiva posible —
  `default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`
  — que además vuelve inerte cualquier respuesta que llegara a
  interpretarse como HTML. `/docs` queda exceptuado porque Swagger UI carga
  de un CDN; en producción no existe (`docs_url=None`), así que la
  excepción solo vive en desarrollo. **Frontend** (`frontend/middleware.ts`)
  usa **nonce por request** con `'strict-dynamic'`: Next inyecta scripts
  inline propios (hidratación, streaming RSC) y sin nonce habría que poner
  `'unsafe-inline'` en `script-src`, que es tanto como no tener CSP contra
  XSS. Concesión conocida y acotada: `style-src` sí lleva
  `'unsafe-inline'` (Next emite estilos críticos inline sin nonce) — el
  vector que importa, ejecución de script, queda cerrado igual.
  Verificado con `curl` contra ambos y sin violaciones en consola.
- ✅ 2026-08-04 **Escaneo de dependencias**: `.github/dependabot.yml` con
  los cuatro ecosistemas (pip, npm, github-actions, docker). Complementa a
  `pip-audit`, que solo *avisa* de una CVE publicada — Dependabot además
  abre el PR que la cierra. Agrupado por ecosistema para no recibir veinte
  PRs sueltos cada lunes; las de seguridad quedan fuera del grupo a
  propósito, para que lleguen solas y se vean. **Sigue pendiente**
  `pip-audit` bloqueante (hoy `|| true`) — ver la sección CI/CD.
- ⬜ **Verificación de firma en webhooks entrantes** (Izipay, Meta):
  documentada en `security.md`, sin implementar — llega con las
  integraciones.
