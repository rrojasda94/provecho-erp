# ADR-025 — Ciclo de caja completo: conteo, relevo firmado y candado del cobro

- Estado: aceptado
- Fecha: 2026-08-04

## Contexto

El slice mínimo de caja (ADR-012, 2026-07-26) creaba los tres registros del
ciclo —apertura, cierre, arqueo— con reconciliación real contra los cobros
en efectivo. Servía para el dashboard, pero dejaba cuatro huecos que el
ROADMAP declaró como deuda y que juntos hacen que el ERP **afirme cosas que
no verificó**:

1. **Se cobraba sin caja abierta.** `POST /sales/ventas/{id}/pagos` no
   miraba si había turno. La plata cobrada fuera de un turno no la espera
   ningún cierre: el faltante recién aparece en contabilidad, semanas
   después, sin responsable posible (RN-MDP-005).
2. **Los montos se tecleaban.** `monto_apertura` y `monto_real` eran
   números en el request; el conteo por denominación (RN-POS-003/007) era
   un JSONB opcional que nadie validaba. Un total que nadie desglosó no es
   un conteo, es una afirmación.
3. **El relevo no lo firmaba nadie.** `relevo_encargado_id` venía en el
   cuerpo del request — un identificador suelto, falsificable por el mismo
   cajero. RN-MDP-002 exige que **quien recibe** se autentique con usuario
   y PIN, en los dos sentidos de la cadena.
4. **Un cierre con faltante solo se podía mirar.** No había flujo de
   corrección, así que la salida práctica era editar la fila en la base.

Además, el POS de tarjeta no existía como entidad (RN-POS-009/010) y el
efectivo desaparecía del sistema al cerrar: `custodia_efectivo` estaba
modelada desde 2026-07-20 y nunca se escribía.

## Decisión

### 1. No se cobra sin caja abierta

`sales.registrar_pago` consulta
`accounting.application.queries_publicas.hay_caja_abierta` y rechaza el
cobro con 409 si el punto de venta no tiene turno. Es una lectura por
**contrato público**: `sales` nunca ve `AperturaCaja`, igual que
`accounting` nunca ve `Venta`.

Vale para **todo medio de pago**, no solo efectivo: el cierre cuadra
efectivo *y* tarjeta contra el reporte de lote (RN-POS-004), así que un
cobro con tarjeta fuera de turno tiene el mismo problema.

Única excepción, explícita: el **replay del push del hub** (ADR-009) pasa
`exigir_caja_abierta=False`. El cobro ya ocurrió en la sucursal con su caja
abierta; volver a exigirlo en la nube rechazaría una venta que físicamente
pasó. El turno vive en el hub y **no se replica** — anotado como deuda.

### 2. El monto sale del conteo, no del teclado

Apertura y cierre reciben `detalle_denominaciones` (`{"50": 2, "0.50": 3}`)
y el servidor suma. Las denominaciones se validan contra el catálogo de
curso legal en soles; una cantidad negativa o no entera es 409.

En la apertura conviven dos números por una razón: `monto_declarado` es lo
que el encargado dice entregar y el conteo es lo que el cajero encuentra.
`diferencia_reportada` **se calcula**, no se teclea — y no bloquea la
apertura (RN-POS-011), solo se reporta.

Un conteo vacío es válido y vale cero (la caja abre aunque no haya llegado
el sencillo). Lo que no se acepta es *no contar*.

### 3. Cada relevo lo firma quien recibe, con su PIN

Apertura, cierre y cada tramo de custodia exigen la **elevación de PIN**
que ya existía para descuentos (RN-AUD-005, `POST /auth/autorizar`), con el
permiso nuevo `accounting.caja_relevar`. El identificador del encargado
sale del token, nunca del cuerpo. Un usuario no puede relevarse a sí mismo:
un relevo de uno solo no prueba nada.

El efectivo sigue vivo después del cierre: `custodia_efectivo` pasa a ser
una máquina de estados real
(`en_caja → en_supervisor → en_contabilidad → disponible`), y nace en
`en_supervisor` porque el cierre ya exigió la firma del encargado — el
primer tramo acaba de ocurrir. Desde `en_supervisor` se puede ir a
`disponible` sin pasar por contabilidad: es el caso de RN-MDP-006 (caja
fuerte del local, monto bajo, se reusa como fondo del día siguiente).

### 4. Un cierre se corrige, no se reescribe

`POST /cajas/cierres/{id}/reabrir` (permiso `accounting.caja_reabrir`,
más autorización por PIN) devuelve el cierre a `en_proceso` y guarda motivo,
autorizador y descuadre anterior en `cierre_caja.correcciones`. Volver a
cerrar **recalcula el mismo registro**: un turno tiene un solo cierre, con
su historial.

Solo mientras el efectivo siga en el local (`en_caja`/`en_supervisor`). Una
vez que llegó a contabilidad, recontar el cajón ya no prueba nada y la
corrección pasa a ser un asiento.

### 5. `pos_tarjeta` como inventario, con terminal de emergencia

Nueva entidad con serie y código de comercio (RN-POS-010) — los dos datos
con los que el operador identifica el terminal en su liquidación. El de
emergencia (RN-POS-009) es una fila con `sucursal_id` en NULL: no pertenece
a ninguna sucursal, se presta a la que lo necesite, y el listado por
sucursal lo incluye siempre.

La apertura verifica los terminales y **no se bloquea** si uno está roto
(RN-POS-011): lo marca `averiado` y publica
`accounting.pos_averiado_reportado` para que contabilidad mande el de
reserva mientras el local sigue vendiendo.

## Alternativas descartadas

- **Exigir caja abierta solo para efectivo.** Más permisivo y más barato en
  tests, pero deja el cobro con tarjeta fuera de todo turno justo cuando el
  cierre tiene que cuadrar su lote (RN-POS-004).
- **Un segundo `cierre_caja` por cada recuento.** Modela el historial
  "gratis", pero rompe el 1:1 apertura↔cierre y obliga a todo lector a
  decidir cuál cierre es el bueno. El historial en `correcciones` mantiene
  una respuesta única a "¿cómo cerró este turno?".
- **`estado` del POS derivado de la última apertura.** Evita una columna,
  pero un terminal averiado un martes seguiría figurando operativo hasta la
  próxima apertura que lo mencione.
- **Replicar el turno de caja al hub y viceversa.** Cerraría la excepción
  del replay, pero el turno es un hecho local de la sucursal y sincronizarlo
  abre preguntas (¿quién cierra un turno que empezó offline?) que no hacen
  falta hoy. Queda como deuda declarada.

## Consecuencias

- Un PDV que no abrió caja **no puede cobrar**. Es el cambio de
  comportamiento más visible y es deliberado.
- Toda apertura y todo cierre necesitan **dos personas presentes**: el
  cajero con su sesión y el encargado con su PIN.
- Permisos nuevos: `accounting.caja_relevar` (supervisor, contador),
  `accounting.caja_reabrir` (supervisor, contador),
  `accounting.pos_administrar` (contador). El rol `supervisor` suma
  `accounting.caja_operar` para cubrir turnos; el candado de no relevarse a
  sí mismo vive en el dominio, no en el rol.
- Eventos nuevos: `accounting.pos_averiado_reportado`,
  `accounting.cierre_caja_reabierto`,
  `accounting.custodia_efectivo_entregada`.
- Migración `f3a1c62d90b4` (tabla `pos_tarjeta`, columna
  `cierre_caja.correcciones`).
- `efectivo_esperado` del reporte de caja ahora descuenta
  `movimiento_caja` (era un techo, no un arqueo) y el arqueo usa el mismo
  cálculo que el cierre.
- Sin pantalla todavía: el ciclo se opera por API. La UI de caja va con las
  pantallas de contabilidad.
