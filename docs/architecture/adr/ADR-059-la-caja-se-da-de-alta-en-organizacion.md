# ADR-059 — La caja se da de alta en Organización

- Estado: aceptado
- Fecha: 2026-08-23
- Contexto: `sales` (punto de venta), `users` (organización)
- Relacionado: ADR-004 (tenant por filtro de aplicación), ADR-025 (ciclo de
  caja), RN-CPP-007 y RN-CPP-008 (serie y correlativo por empresa), RN-CPP-009
  (la NC numera aparte), RN-POS-005 (autoatención cobra adelantado),
  RN-MDC-001 (modalidades configurables)

## Contexto

`punto_venta` —la caja de una sucursal, que carga las series SUNAT con las que
el local emite— **solo existía en el seeder**. No había `POST`, ni `PATCH`, ni
pantalla: el único endpoint era `GET /sales/puntos-venta`.

Eso se rompió en cuanto hubo un entorno que no fuera el de pruebas. El
servicio `init` de staging corre `src.seeders.seed`, que no siembra ninguna
caja (las que sí lo hacen —`pdv_demo`, `e2e`— no corren ahí). Un tester entra
al PDV y recibe "La sucursal no tiene puntos de venta"; el mensaje le pedía
configurar una caja **sin decir dónde**, porque no había dónde.

La salida fácil era sembrar una caja en `seed.py`. No sirve: el seeder no
puede inventar la serie SUNAT que el negocio va a usar de verdad, y una serie
inventada que empieza a emitir es peor que no poder emitir.

## Decisión

### 1. El alta vive en `sales`, pero la firma `organizacion.gestionar`

Los endpoints son `POST` y `PATCH /api/v1/sales/puntos-venta` —el modelo es
dominio de `sales` y no se muda—, pero **no** los gatea un permiso `sales.*`.
Los gatea `organizacion.gestionar`, el mismo de empresas, marcas, sucursales y
almacenes.

Asignar una serie SUNAT es un acto de **identidad fiscal de la empresa**, del
mismo orden que fundar el local o fijar el RUC. No es configurar el salón: un
supervisor con `sales.gestionar_mesas` acomoda mesas, no inventa series de
facturación. Un permiso `sales.gestionar_puntos_venta` habría modelado el acto
como si fuera lo segundo.

Esto es una **excepción deliberada** a "el prefijo del permiso sigue al
módulo del router". Se acepta porque el permiso describe quién puede hacer el
acto, no dónde vive el código; y porque la alternativa obligaba además a
mandar la pantalla lejos de Sucursales (el shell filtra el módulo por
`prefijoPermiso`, así que una pantalla en `/organizacion` gateada por un
permiso `sales.*` habría dado "Sin permiso" a quien sí puede entrar).

La pantalla, en consecuencia, es `/organizacion/puntos-venta`, entre
Sucursales y Almacenes: es el paso siguiente a dar de alta un local.

El `GET` acepta **cualquiera de los dos** (`sales.leer` o
`organizacion.gestionar`): el cajero tiene el primero y lo necesita para
abrir el PDV; el administrador que da de alta las cajas puede no tener ningún
permiso de venta. Mismo criterio que `GET /accounting/cajas/abiertas`.

### 2. La unicidad de serie se valida en el caso de uso, no en el esquema

RN-CPP-007 dice que el correlativo es único por `(empresa, serie)`: dos cajas
de la misma empresa que compartan una serie se pisan al emitir. La validación
vive en `sales/application/puntos_venta.py` y **no hay UNIQUE en la tabla**.

Tres razones:

1. **No es expresable ahí.** `punto_venta` no tiene `empresa_id` (se alcanza
   por `sucursal`) y la regla abarca cuatro columnas des-pivoteadas
   (`serie_boleta`, `serie_factura`, `serie_nc_boleta`, `serie_nc_factura`).
   Un UNIQUE real exigiría denormalizar `empresa_id` —con backfill y la
   obligación de mantenerlo sincronizado— o una tabla hija de series. Las dos
   son cambios de modelo más grandes que la funcionalidad que los motiva.
2. **El candado que importa ya existe, en la otra punta**:
   `UNIQUE(comprobante.empresa_id, serie, correlativo)` (RN-CPP-008). Dos
   cajas con la misma serie chocan **ahí**, ruidosamente, sin llegar a emitir
   un duplicado. La validación de aplicación evita el error antes de que
   ocurra; no es la última línea de defensa.
3. **Costo desproporcionado.** Una migración con UNIQUE se prueba contra
   Postgres con downgrade y upgrade, hay filas vivas en staging, y dos UNIQUE
   con la misma primera columna chocan por nombre de constraint. Todo eso
   para una tabla de una fila por caja.

El costo aceptado: una escritura directa a la base puede meter una serie
duplicada sin que nada la ataje hasta el momento de emitir. Se asume porque
la única escritura directa que existía es justamente la que este cambio
reemplaza.

### 3. Se puede corregir la serie de una caja que ya emitió

`PATCH` permite cambiar las cuatro series. No hace falta guarda: la serie del
comprobante es una **copia congelada al emitir**, así que lo ya emitido no se
toca, y el correlativo nuevo arranca en el máximo de la serie nueva. Lo que
no se permite es mudar la caja de sucursal — sus comprobantes, aperturas y
cierres cuelgan de ese local.

### 4. Las reglas que el seeder daba por buenas ahora se validan

Porque las tipeaba a mano: formato de serie (`^[BF][A-Z0-9]{3}$`), las cuatro
series distintas entre sí (RN-CPP-009), autoatención con pago adelantado
(RN-POS-005), `hardware_id` rechazado en canal `web` —no anulado en silencio,
porque quien lo mandó cree que tiene una caja física—, y modalidades como
subconjunto no vacío (RN-MDC-001, donde `null` sigue significando las tres).

La sucursal se verifica explícitamente aunque haya FK: en SQLite la FK no se
valida, así que sin ese chequeo el test pasaba en verde y Postgres devolvía un
500 en producción.

## Consecuencias

- Una sucursal nueva se pone a vender sin tocar la base.
- No hay migración: el modelo tenía los diez campos desde el principio.
- `PuntoVentaOut` ahora expone `serie_nc_*` y `hardware_id`, que existían y no
  se veían. Sin la primera no se podía saber si una caja puede acreditar lo
  que emitió.
- Queda pendiente (deuda en `docs/roadmap/deuda/modulo-sales.md`): baja o
  desactivación de una caja, el campo "caja principal" de RN-POS-008,
  `datos_minimos_por_modalidad` y `kpis` sin pantalla, y `serie_nc_*` fuera de
  la réplica offline.
