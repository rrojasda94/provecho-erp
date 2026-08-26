- **Un almacén creado por error ya se puede quitar** (2026-08-26). El endpoint
  `DELETE /almacenes/{id}` existía desde 2026-08-08 y hacía lo correcto —baja
  lógica, auditada, negada con 409 si otros almacenes se abastecen de este—,
  pero **ninguna pantalla lo llamaba**: quien se equivocaba al crear uno se
  quedaba con el registro en la lista y en todos los selectores de compras,
  inventario y producción para siempre. Ahora hay botón «Dar de baja» en
  Organización → Almacenes.
- **Y la vuelta: `POST /almacenes/{id}/reactivar`.** La baja no mira el stock
  —vive en `inventory` y `users` no importa el dominio de otro módulo—, así
  que la única red posible es poder deshacerla. Sin ella el problema se
  repetía al revés: `AlmacenRepo.get/list` filtran `deleted_at`, de modo que
  un almacén dado de baja por error desaparecía de la interfaz **para
  siempre**. Es idempotente: reactivar uno que nunca se dio de baja no es un
  error, es un no-op —dos clicks del mismo botón no tienen por qué producir un
  409 que no significa nada—.
- **`GET /almacenes?incluir_baja=true`**, y solo con `organizacion.gestionar`.
  El catálogo plano sigue abierto a cualquier usuario autenticado —compras
  necesita elegir un destino—, pero un almacén de baja no puede aparecer en un
  selector: si aparece, alguien termina mandándole una orden de compra. Los
  dados de baja se ven tachados y con su botón de recuperación únicamente en
  la pantalla de Organización, que es la única que puede recuperarlos.
