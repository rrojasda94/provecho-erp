# Módulo `assets` — Activos, mantenimiento y vigencias

## Objetivo

Registro operativo de los equipos y vehículos del grupo: kilometraje y
consumo de combustible, cronograma de mantenimiento con aviso anticipado, y
documentos con fecha de vencimiento (SOAT, revisión técnica, licencia de
funcionamiento, carné de sanidad, licencia de conducir, etc.). Pedido
directo del usuario (2026-09-09) — nada de esto existía antes (ADR-098).

**No es dueño del ciclo de compra ni de la depreciación.** Un activo se
compra en `purchases` (OC tipo `activo`, deuda declarada de ese módulo) y
se depreciará en `accounting` (deuda declarada). `assets` es lo que pasa
**después** de comprado: usarlo, mantenerlo, y saber cuándo sus papeles
vencen.

## Entidades

`activo` (equipamiento o vehículo, `empresa_id` propio), `vehiculo`
(extiende `activo` 1:1: placa, tipo, tenencia, kilometraje_actual),
`lectura_odometro` (historial de kilometraje, nunca retrocede — RN-VEH-005),
`carga_combustible` (liga un comprobante ya **recibido** en `purchases` al
vehículo, calcula rendimiento y detecta consumo anómalo — RN-VEH-006/007),
`plan_mantenimiento` (frecuencia por días y/o km, con anticipación de aviso
configurable — RN-MNT-001/005), `orden_mantenimiento` (ejecución de un plan
o adelanto por avería — RN-MNT-002/003/004), `documento_vigencia`
(polimórfico: sujeto `activo`/`sucursal`/`empresa`/`trabajador` — RN-DOC-001..004).

`flota` y `repuesto_compatibilidad` quedan diferidos (deuda declarada,
`docs/roadmap/deuda/modulo-assets.md`). Detalle completo en
`docs/architecture/data-model.md` §Recursos.

## Casos de uso

- Alta de un activo (equipamiento o vehículo con sus datos propios en la
  misma llamada), edición, baja.
- Registrar kilometraje manual, o vía una carga de combustible o una orden
  de mantenimiento realizada.
- Registrar una carga de combustible ligando un comprobante que Compras ya
  recibió (`GET /comprobantes-disponibles` los lista sin usar); calcula
  `km_recorridos` y `rendimiento_km_gal` contra la carga anterior, y marca
  `anomalo` si cae muy por debajo del promedio de las últimas cargas
  (parámetro `assets/tolerancia_consumo_pct`, ADR-014).
- Crear y editar un plan de mantenimiento; su estado (`al_dia`/`proximo`/
  `vencido`) se calcula al leer, nunca se guarda.
- Crear una orden de mantenimiento (desde un plan o por avería reportada),
  iniciarla (el activo pasa a `en_mantenimiento`), realizarla (actualiza el
  plan y el odómetro si trae km, el activo vuelve a `operativo`) o
  cancelarla.
- Crear un documento con vencimiento, editarlo, renovarlo (crea uno nuevo y
  encadena el viejo — nunca sobrescribe la fecha), adjuntarle un archivo
  (metadata, mismo patrón que `marketing.application.adjuntos`).
- `GET /cronograma`: agenda unificada de mantenimientos y documentos
  próximos/vencidos, ordenada por fecha — la pantalla de entrada del
  módulo.
- Barrido diario (`assets.barrer_vencimientos`, Celery beat 06:30) que
  evalúa todos los planes y documentos activos y publica el aviso que
  corresponda, una sola vez por ventana.

## Eventos

Publica (consumidos por `reports`, que se suscribe a todo su catálogo sin
que `assets` necesite `listeners.py` propio):

- `assets.mantenimiento_proximo` / `assets.mantenimiento_vencido`
- `assets.documento_por_vencer` / `assets.documento_vencido`
- `assets.consumo_anomalo`

Detalle de payload en `docs/architecture/events.md`.

## Endpoints (`/api/v1/assets`)

Permisos: `assets.leer`, `assets.gestionar` (activos, planes, documentos),
`assets.mantener` (lecturas, cargas, órdenes), `assets.dar_baja`,
`assets.proponer_parametro` (generado automático por módulo, ADR-014).

- `POST/GET /activos`, `GET/PATCH /activos/{id}`, `POST /activos/{id}/baja`.
- `POST/GET /activos/{id}/lecturas-odometro`.
- `POST/GET /activos/{id}/cargas-combustible`, `GET /activos/{id}/consumo`.
- `GET /comprobantes-disponibles`.
- `POST/PATCH /planes`, `GET /planes`, `GET /activos/{id}/planes`.
- `POST /ordenes-mantenimiento`, `GET /ordenes-mantenimiento[/{id}]`,
  `POST /ordenes-mantenimiento/{id}/{iniciar|realizar|cancelar}`.
- `POST/GET/PATCH /documentos`, `GET /documentos/{id}`,
  `POST /documentos/{id}/renovar`, `POST/GET /documentos/{id}/adjuntos`.
- `GET /cronograma`.

## Reglas

RN-VEH-001..007, RN-MNT-001..005, RN-EQP-001..004, RN-RPT-001..004,
RN-DOC-001..004 en `docs/domain/business-rules.md`.

## Dependencias

- `shared.models.Comprobante`/`Archivo` (transversales).
- `users.infrastructure.models` (Empresa, Sucursal — excepción `*` de
  `tests/test_arquitectura.py`).
- `purchases.application.queries_publicas.proveedor_para_guia` (contrato
  público, nombre/RUC del proveedor de servicio).
- `rrhh.application.queries_publicas.trabajador_resumen` (contrato público
  nuevo, para validar el sujeto `trabajador` de un documento).

Nunca al revés: ningún otro módulo importa el dominio de `assets` todavía.
