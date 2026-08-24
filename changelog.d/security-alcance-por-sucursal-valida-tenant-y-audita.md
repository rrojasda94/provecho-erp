- **Asignar un local al alcance de una cuenta no validaba tenant ni dejaba
  rastro** (2026-08-24). `POST/DELETE /users/{id}/sucursales` aceptaba
  cualquier `sucursal_id`: quien administraba las cuentas de su empresa podía
  colgar un usuario a la sucursal de **otra empresa del grupo** y darle acceso
  a datos ajenos, sin que quedara escrito. Ahora las dos operaciones exigen
  que la sucursal sea de la empresa de quien administra —el superusuario sigue
  operando sobre todo el grupo, igual que en el alta de sucursales— y las dos
  quedan en `audit_log`. Se audita también el quite porque es la otra mitad de
  "quién podía ver este local y desde cuándo".
