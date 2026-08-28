- **El pad de asistencia solo marca desde un terminal autorizado** (ADR-073,
  RN-RRHH-023). La sesión de la cuenta de servicio del pad era exportable a
  cualquier navegador: con el mismo token, `/asistencia` marcaba igual desde
  el celular de un supervisor que nunca llegó al local. Ahora cada sucursal
  enrola su tablet una vez (código de 6 dígitos, 30 minutos de vigencia,
  `POST /rrhh/terminales` — nueva pantalla Organización/RRHH → Terminales) y
  el pad manda un secreto propio en cada marcación; sin terminal activo de
  esa sucursal, 403 aunque el PIN sea correcto.
- **Cada marcación queda con su evidencia** (RN-RRHH-024): terminal, IP,
  ubicación y foto, ninguno obligatorio ni bloqueante — sin permiso de
  cámara o de GPS se marca igual con esos campos en `NULL`. La distancia a
  la sucursal se observa contra `sucursal.radio_marcaje_m` (nuevo,
  configurable por local); nunca se bloquea por ella, porque el GPS de una
  tablet fija bajo techo se equivoca por decenas de metros. La foto se
  purga a los 90 días (`rrhh_marcaje_foto_retencion_dias`); el resto de la
  evidencia queda.
- **Fix de infraestructura de paso**: el proxy de Next
  (`app/api/proxy/[...ruta]/route.ts`) no reenviaba `X-Forwarded-For` a la
  API — cada marcación (y cada request del PDV) quedaba auditada con la IP
  del contenedor `web`, nunca la del cliente real. Requiere que
  `FORWARDED_ALLOW_IPS` en producción confíe también en ese salto (cambio de
  despliegue, ver Deuda técnica → Módulo rrhh).
