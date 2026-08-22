- **`.env.example` volvió a documentar toda la configuración** (2026-08-22).
  Se había quedado 22 variables atrás de `src/config/settings.py`: faltaban
  `ZONA_HORARIA` —de la que sale "qué día es hoy" para el ERP, y sin ella un
  cierre de las 20:00 hora Perú cae al día siguiente porque Docker corre en
  UTC—, `HSTS_MAX_AGE_SEGUNDOS`, los tres límites de la consulta de DNI/RUC
  (`CONSULTA_DOCUMENTO_*`, ADR-041) y **los seis umbrales de negocio**
  (`PURCHASES_UMBRAL_APROBACION_OC`, `ACCOUNTING_UMBRAL_APROBACION_PAGO`,
  `INVENTORY_MARGEN_AJUSTE_PCT`, `PRODUCTION_COSTO_HORA_MANO_OBRA`,
  `RRHH_RMV_VIGENTE`, `RRHH_PLAZO_CONSERVACION_POSTULANTE_MESES`). Estos
  últimos son los que deciden si una OC o un pago pasan solos o piden
  aprobación: existían en el código como valor semilla y no había ni un
  renglón que le dijera al negocio que se podían mover. También se agregaron
  `PROVECHO_IMAGE` y `PROVECHO_WEB_IMAGE`, que `docker-compose.prod.yml`
  exige para desplegar.
- **La deriva ahora la ve el CI, no el día del incidente.** Tres pruebas en
  `tests/test_settings.py`: que todo campo de `Settings` esté documentado en
  `.env.example` o en `.env.hub.example`, que copiar `.env.example` tal cual
  —el primer paso del README— produzca una configuración que **arranca**, y
  que el ejemplo no lleve credenciales de verdad. La última no es paranoia
  barata: `.env.example` sí se commitea, y un JWT copiado del `.env` real
  queda en el historial de git para siempre; rotarlo después es un trámite
  con el proveedor, no un `git revert`.
- **`NUBEFACT_URL` y `NUBEFACT_TOKEN` salieron del ejemplo.** Factiliza lo
  reemplazó el 2026-07-26 y ningún módulo las lee; seguían ahí invitando a
  configurar un proveedor descartado.
- **`GOOGLE_API_KEY` pasó a llamarse `GOOGLE_MAPS_BROWSER_KEY`**, que es lo
  que de verdad es: una clave de navegador restringida por referrer que
  consume el frontend. Ningún código la lee todavía, así que el cambio de
  nombre no rompe nada — y evita que alguien pegue ahí una clave de servidor
  creyendo que el backend la usa.
- Se decidió **no** documentar `APP_NAME`, `APP_VERSION` ni `JWT_ALGORITHM`:
  nadie los ajusta por entorno y ofrecerlos en el ejemplo solo invita a
  romper cosas. Quedan en una lista explícita dentro de la prueba, no como
  olvido.
