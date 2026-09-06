# Historial — Módulo `users` (auth, RBAC, organización)

Estado vigente: ✅ Completo — auth JWT+PIN (Argon2id), RBAC con restricciones
JSONB, refresh rotativo con detección de reuso, lockout, token de agente IA,
CRUD de organización (grupo/empresa/marca/sucursal/almacén), reseteo de PIN,
consulta RENIEC/SUNAT vía Factiliza y contexto de tenant/auditoría base están
todos implementados y en uso; los ajustes más recientes (2026-08-28 a
2026-09-04) son refinamientos de la sesión (renovación automática, expiración
a 8 h, aviso al cliente cuando la sesión muere), no deuda pendiente. No existe
`docs/roadmap/deuda/modulo-users.md` en el índice de Deuda técnica del
ROADMAP, es decir el módulo no tiene deuda propia declarada aparte de la
transversal.

## Cronología

### 2026-07-14 — Pendiente: estrategia de tenant (RLS vs. filtro de aplicación)
Pendiente de decisión técnica antes de migrar: estrategia de tenant
(RLS de Postgres vs. filtro a nivel de aplicación) — no definida aún en
docs, definirla al iniciar esta fase.

**Estado vigente:** resuelto el 2026-07-20 — ver el bloque **ADR-004** más
abajo: tenant por filtro de aplicación, no RLS.

### 2026-07-20 — ADR-004: tenant por filtro de aplicación
ADRs normalizados a 3 dígitos; ruta corregida en CLAUDE.md; **ADR-004**
nuevo: tenant por filtro de aplicación (`empresa_id` obligatorio +
tests; RLS como refuerzo futuro).

### 2026-07-20 — Fase de procesos: `users` primero en el orden sugerido
1. `users`: auth (login PIN → JWT/refresh), RBAC, contexto de tenant, auditoría base.
2. Organización: grupo → empresa → marca → sucursal → almacén (vive en `users` o módulo `organization`).
3. `inventory`: artículos, stock por almacén, movimientos.
4. `purchases`: proveedores, OC, recepción → entrada a almacén central.
5. Solicitudes + transferencias central → local.
6. `sales`: PDV, recetas, descuento automático de insumos, pagos, Nubefact.
7. Producción, contabilidad, RRHH, resto de módulos.

**Estado vigente:** este orden es el plan previo a construir el módulo; la
implementación real llegó el 2026-07-25 (ver bloque siguiente) confirmando a
`users` como primer módulo de código del ERP.

### 2026-07-25 — Módulo `users` (auth JWT + PIN + RBAC): slice base
Slice auth+CRUD implementado: 7 tablas RBAC (`rol`, `permiso`, `usuario_rol`,
`rol_permiso`, `usuario_sucursal`, `refresh_token`, `audit_log`) + lockout en
`usuario`. Login/refresh(rotativo+detección de reuso)/logout/me + CRUD admin
de usuarios/roles/permisos/asignaciones. Argon2id, JWT, `require_permission`
deny por defecto. `docs/security/authorization.md`.

### 2026-07-27 — Seeders (admin / PIN 123456, org base)
`src/seeders/seed.py` (idempotente, prohibido en prod): matriz de roles/permisos
semilla, `admin`/PIN `123456` y la **organización real** del grupo — empresa
Majambo EIRL (RUC 20450311520, Jr. Ramón Castilla 248 - Tarapoto, zona
`amazonia_ley27037`), marca Charlie's Pizzas **licenciada** a la empresa
(`licencia_marca`), sucursales `CH1` (Jr. Ramón Castilla 248) y `CH2` (Jr.
Lamas 299) activas y alquiladas (RN-IMP-004), almacén central `WH1`
(`sucursal_id` NULL). Requirió `almacen.direccion` (migración `e5a1c93b7d40`):
el central no cuelga de ninguna sucursal y no había dónde guardar su
ubicación. Correr: `python -m src.seeders.seed`. **CRUD de organización por
API: ✅ 2026-08-08** — el seeder deja de ser la única vía para crear
empresa/marca/sucursal/almacén. Diferido: almacenes de sucursal de CH1/CH2
(no pedidos; su mín./máx. por SKU depende de datos de operación inexistentes).

### 2026-08-02 — ADR-022: restricciones JSONB por permiso
Restricciones JSONB por permiso: aplicadas desde 2026-08-02 (ADR-022, ver
Deuda técnica).

### 2026-08-08 — Token de API para agentes (ADR-032)
**Token de API para agentes** (2026-08-08, ADR-032, migración
`b3f7d21a9c04`): una cuenta `tipo=agente_ia` se autentica con `token_agente`
(256 bits, solo el SHA-256 se persiste, revocable de a uno) en vez de PIN —
un PIN de 6 dígitos son 20 bits en un `.env` y su lockout apaga
integraciones. `get_claims` distingue por el prefijo `prv_` y arma **los
mismos claims**: el RBAC no cambia.

### 2026-08-08 — CRUD de organización por API
**CRUD de organización por API** (2026-08-08, permiso propio
`organizacion.gestionar`): grupo, empresa, marca, licencia de marca,
sucursal y almacén; sin cambios de esquema.

### 2026-08-08 — Auditoría (audit_log) transversal (ADR-031)
Auditoría (audit_log) | ✅ 2026-08-08 | Transversal (ADR-031):
`src/shared/auditoria.py` es el único escritor, `GET /api/v1/auditoria`
(permiso `auditoria.leer`) el lector. Cinco módulos nuevos dejan rastro;
`empresa_id` + índices en migración `b3d9f1c2a077`. Pendiente la purga por
antigüedad (ver Deuda técnica → Protección de datos).

### 2026-08-12 — Reseteo de PIN y consulta de documento (ADR-041)
**Reseteo de PIN y consulta de documento** (2026-08-12, ADR-041, migración
`a7c04e3b91d5`): un PIN olvidado no se recuperaba —Argon2id— y el frontend
documentaba un autoservicio que no existía. `users.resetear_pin` (permiso
propio, a `rrhh_admin`) devuelve la cuenta al PIN por defecto y **la
bloquea**: `get_current_user` lee `usuario.debe_cambiar_pin` de la base —no
de un claim, que se congela al emitir— y responde 403 a todo salvo verse,
cambiarlo y salir; se revocan sus sesiones y se limpia el lockout. Suma
`POST /users/me/pin` (sin permiso, con PIN actual). Y `GET
/consulta/{dni,ruc}/{n}` en `core` expone al fin el cliente de Factiliza que
existía sin consumidor: botón "Buscar" en Personas y Proveedores que
prellena sin decidir, permiso propio `consulta.documento` porque cada
consulta gasta cuota y trae datos de quien todavía no es nadie en el
sistema.

### 2026-08-15 — La consulta, visible y con cuota
**La consulta, visible y con cuota** (2026-08-15): el botón faltaba en
Ventas → Clientes —la pantalla que promete que «SUNAT manda sobre la razón
social tecleada»— y ningún punto de montaje miraba el permiso, así que un
`contador` lo veía y se comía un 403; el gate vive ahora dentro del
componente y `permisos` es prop obligatoria. Cierra además la deuda del
rate limit: `GET /consulta/{dni,ruc}/{n}` cuenta **por usuario y por IP**
(20 y 60 por minuto, configurables) reusando `core/rate_limit.py` —fail-open
incluido—, porque en un local todas las cajas salen por la misma dirección y
limitar solo por IP castiga al equipo entero por uno.

### 2026-08-22 — La consulta llega a caja (addendum de ADR-041) y RRHH
**La consulta llega a caja** (2026-08-22, addendum de ADR-041): faltaba el
punto donde más se teclea un documento —el PDV—, el único de los cuatro y
justo aquel por el que el `cajero` tiene el permiso. Quedó en sus **dos**
momentos: el alta de cliente y el receptor del comprobante. En caja hay un
solo campo para los dos documentos, así que el modo `auto` deja que el largo
decida el padrón (8 → RENIEC, 11 → SUNAT, la misma regla que ya elegía
boleta o factura, RN-CPP-003, aislada en `frontend/lib/documento.ts` con su
prueba); un largo intermedio no se consulta, porque una consulta a ciegas
gasta cuota para volver con un "no encontrado" que no significa nada.
Montarlo obligó a una segunda forma del mismo botón: `BuscarDocumento`
escribe en el DOM del `<form>` y el PDV lleva estado de React, así que
`ConsultaDocumento` recibe el número y devuelve la respuesta cruda por
`onDatos` — se descartó rehacer el diálogo de cobro como formulario no
controlado. El campo de documento del alta acepta ahora los dos largos: con
11 el cliente nace jurídico, que es lo que `crear_cliente` ya hacía y la
pantalla no dejaba pedir.

**Y RRHH, donde más pesa**: `contratar_postulante` creaba la `persona` con
lo que el candidato escribió de sí mismo en el formulario **público** —sin
sesión ni permiso—, y con ese nombre se firma el contrato y se declara a
SUNAT; `sales` y `purchases` ya pasaban el documento por `nombres_desde_dni`
y RRHH no. Ahora el servidor lo aplica aunque nadie apriete el botón, y el
diálogo de contratar suma nombres/apellidos editables para poder verlo antes
(precedencia RENIEC > lo revisado > lo declarado; con carné o pasaporte no
se consulta). De paso, un **401 del proveedor se llamaba "respuesta
ilegible"** —solo el 404 vacío y el 5xx se trataban aparte, así que el 401
moría en el parseo de JSON— y mandaba a buscar un error de formato donde lo
que hay que revisar es la credencial.

### 2026-08-24 — Dónde trabaja alguien y qué datos alcanza son dos cosas (ADR-062)
✅ 2026-08-24 **Dónde trabaja alguien y qué datos alcanza son dos cosas**
(ADR-062, migración `b6d29f10c47e`, RN-RRHH-019). No se podía asignar un
trabajador a una sucursal ni un supervisor a varias: `trabajador` no tenía
local (la asistencia no tenía a qué sucursal atribuirse) y `usuario_sucursal`
tenía endpoints desde el slice inicial **pero ninguna pantalla** — fuera del
seeder nadie repartía alcance. Ahora `trabajador.sucursal_id` (nullable) es
el **centro de labores**, un hecho laboral de RRHH, y `usuario_sucursal`
sigue siendo el **alcance de datos** de la cuenta; se editan por separado en
RRHH → Trabajadores y Usuarios → Cuentas. Un supervisor sobre varios locales
son **varias filas**: se descartó una tabla `zona` porque hoy ningún reporte,
permiso ni regla la nombra —sería una entidad con tenant, seeder y CRUD para
ahorrar dos clics—. De paso se cerraron dos agujeros del endpoint que ya
existía: no validaba tenant (se podía dar acceso al local de otra empresa del
grupo) y no auditaba. Nuevo `GET /users/{id}/sucursales`. Tests en
`tests/test_rrhh.py` y `tests/test_organizacion_crud.py`.

### 2026-08-26 — Un almacén creado por error ya se puede quitar
**Un almacén creado por error ya se puede quitar** (2026-08-26): el `DELETE
/almacenes/{id}` existía desde 2026-08-08 y **ninguna pantalla lo llamaba**,
así que el registro se quedaba en la lista y en los selectores de compras,
inventario y producción para siempre. Suma el botón en Organización →
Almacenes y su vuelta, `POST /almacenes/{id}/reactivar` (idempotente): como
la baja no mira el stock —frontera de módulos—, poder deshacerla es la única
red posible; sin ella el problema se repetía al revés, porque `AlmacenRepo`
filtra `deleted_at` y el almacén desaparecía de la interfaz. Los de baja se
listan solo con `?incluir_baja=true`, que exige `organizacion.gestionar`:
uno de baja en un `<select>` termina recibiendo una orden de compra.

### 2026-08-28 — Sesión que se renueva sola + sucursal fresca con selector (ADR-073)
Se probó el PDV en producción con dos usuarios nuevos de trabajadores en CH1
y CH2, y salieron doce cosas. Tres causas raíz explican la mitad: el frontend
nunca renovaba el token, el PDV leía su sucursal del JWT congelado, y el
borrador no existía fuera de la memoria del navegador.

| Tanda | Qué | Estado |
|---|---|---|
| 1 | Sesión que se renueva sola + sucursal fresca con selector (ADR-073) | ✅ 2026-08-28 |

(Extraído de la tabla completa de "Parche del PDV — hallazgos del turno de
prueba (0.7.8, desde 2026-08-28)"; el resto de las filas de esa tabla —
borrador del PDV, aumento en el KDS, número de mesa, apertura/cierre de
caja, bloqueo de pantalla, alta de cliente, despacho, cupón/descuento,
notas de cocina, motor de promociones— pertenece al historial de `sales`,
no al de `users`.)

### 2026-08-30 — La sesión muere con el navegador y a las 8 h quietas (ADR-084)
Siete reportes. **Cinco no eran código faltante en el backend**: eran
superficies que nunca se construyeron sobre endpoints que ya existían y ya
tenían pruebas verdes — el patrón que se repite desde la 0.8.0 y que este
parche corta. Los otros dos sí eran decisiones pendientes: cuánto dura una
sesión y de dónde sale la cuenta contable de lo que se compra y se vende.

| # | Qué | Estado |
|---|---|---|
| 3 | La sesión muere con el navegador y a las 8 h quietas (ADR-084) | ✅ 2026-08-30 |

(Extraído de la tabla completa de "Parche 0.9.1 — tercer turno de prueba en
staging (2026-08-30)"; el resto de las filas —enlace al BI desde el
dashboard, botón de vuelta del despacho, pantalla de stock/kardex, ciclo de
la OC y factura de proveedor, cuenta contable heredada de la categoría,
recuperación del pedido en curso, entrada de stock manual— pertenece a los
historiales de `sales`, `inventory` y `accounting`.)

### 2026-09-04 — La sesión muere y el cliente no se entera (ADR-088)
| Bloque | Hallazgos | Estado |
|---|---|---|
| `fix/sesion-expirada-cliente` | #10 la sesión muere y el cliente no se entera: bucle del KDS, campana muda, borradores del PDV que dejan de guardarse en silencio (ADR-088) | ✅ 2026-09-04 |

(Extraído de la tabla completa de "Auditoría del 2026-08-30 — Ola 2
(2026-09-04)"; el resto de los bloques de esa ola —gates RBAC de botones en
contabilidad/trabajadores/artículos/devoluciones, migración de diálogos,
mermas y traslados de inventario— son correcciones de UI en otros módulos
que usan permisos ya existentes de `users`, no cambios al dominio de
`users`, y por eso no se incluyen aquí completos.)

## Fuentes

- Línea 19 de ROADMAP.md: fila F0 "Módulo `users` (auth JWT + PIN + RBAC)" —
  bloque narrativo único con fechas internas 2026-07-25, 2026-08-02
  (ADR-022), 2026-08-08 (ADR-032 token_agente; CRUD organización), 2026-08-12
  (ADR-041 reseteo PIN/consulta documento), 2026-08-15 (consulta visible),
  2026-08-22 (consulta llega a caja + RRHH nombres_desde_dni), 2026-08-26
  (almacén se puede quitar). Repartido en los bloques de cronología
  correspondientes.
- Línea 21 de ROADMAP.md: fila F0 "Seeders (admin / PIN 123456, org base)" —
  incluye la nota de estado "CRUD de organización por API: ✅ 2026-08-08".
- Línea 46 de ROADMAP.md: fila F0 "Auditoría (audit_log)" — ADR-031,
  transversal, tocado en `users` como contexto de auditoría base.
- Líneas 68-77 de ROADMAP.md: encabezado e intro de "Parche del PDV —
  hallazgos del turno de prueba (0.7.8, desde 2026-08-28)" + fila de la
  tabla correspondiente a ADR-073 (sesión que se renueva sola).
- Líneas 222-235 de ROADMAP.md: encabezado e intro de "Parche 0.9.1 —
  tercer turno de prueba en staging (2026-08-30)" + fila de la tabla
  correspondiente a ADR-084 (duración de sesión).
- Líneas 260-278 de ROADMAP.md: encabezado e intro de "Auditoría del
  2026-08-30 — Ola 2 (2026-09-04)" + fila de la tabla correspondiente a
  `fix/sesion-expirada-cliente` (ADR-088).
- Líneas 517-531 de ROADMAP.md: pendiente de decisión "Dónde trabaja alguien
  y qué datos alcanza son dos cosas" (ADR-062, `trabajador.sucursal_id` vs.
  `usuario_sucursal`).
- Líneas 574-605 de ROADMAP.md: índice de "Deuda técnica pendiente
  (backlog)" — verificado, no contiene ningún archivo `modulo-users.md` ni
  texto narrativo sobre `users` mezclado; es solo el índice a
  `docs/roadmap/deuda/*.md` y no se copió nada de aquí.
- Líneas 688-729 de ROADMAP.md: "Modelado de BD — siguiente sesión" —
  párrafo final (727-729) sobre la decisión pendiente de estrategia de
  tenant (RLS vs. filtro de aplicación).
- Líneas 1079-1088 de ROADMAP.md: "Revisión de consistencia y correcciones
  (2026-07-20)" — bullet de ADR-004 (tenant por filtro de aplicación).
- Líneas 1405-1413 de ROADMAP.md: "Fase de procesos (tras el modelado de
  BD)" — lista completa de 7 puntos; se copió el punto 1 y 2 (users +
  organización) tal cual, y se incluyó la lista completa como contexto del
  orden planeado.

Rangos de ROADMAP.md revisados en su totalidad para cobertura (sin
extraer nada adicional relevante a `users` fuera de lo listado arriba):
1-30 (tabla F0 completa), 31-66 (resto de F0), 67-126 (parches PDV y
desplegables), 127-190 (parches compras/inventario/ventas), 191-260
(auditoría Ola 1 y parches 0.9.x), 260-343 (Ola 2, contabilidad-no-asienta,
Ola 3, Ola 4), 343-373 (catálogo modelo Odoo, no relevante a `users`),
374-443 (pendientes de decisión: parámetros operativos, RBAC de aprobación
de OC/ajustes — verificado, son decisiones de rol específicas de `purchases`
e `inventory`, no de `users`), 444-573 (resto de pendientes: reportes,
BPMN de áreas, accesibilidad, ADR-062 de sucursal/alcance, staging),
574-605 (índice de deuda técnica, sin contenido de `users`), 606-1413
(orden sugerido de desarrollo completo: slices de Venta, Apertura de
Caja/Sucursal, RRHH, Compras, Comercial, Almacén-Logística, núcleo de
Venta/Cobro/Caja, revisión de consistencia, Producción, Gerencia, Marketing,
Cumplimiento de pedido, y la fase de procesos final — verificado que las
menciones de "Supervisor"/RBAC dentro de esas secciones son de alcance de
otros procesos, no del dominio de `users`, salvo los bloques ya extraídos).
