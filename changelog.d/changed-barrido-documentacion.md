- **Documentación al día con el código (barrido 2026-09-18).** Los slices
  recientes (delivery, assets, supervision, storefront) actualizaron sus docs
  propios pero no los transversales, que seguían describiendo 5–8 módulos de
  13. Ahora `CLAUDE.md`, `README.md`, `overview.md`, `domain-model.md`,
  `diagrams/modules.md`, `product/modules.md` y `module-guide.md` listan los
  13; `module-guide` pasa de 7 a 7 + 5 registros condicionales (Celery beat,
  router público, emisiones de reporte, destinos, settings).
  `events.md` suma los 10 eventos que se publicaban sin estar catalogados y
  marca como planificados los 4 que nadie publica; `sales.pago_registrado`
  nunca existió — es `sales.venta_pagada`, y la deuda de accounting que decía
  que la 1212 no se cancela estaba resuelta desde 2026-09-05.
  `data-model.md` documenta 4 tablas faltantes y renumera secciones (9–13).
  En `business-rules.md` dos series de códigos estaban duplicadas: Empaques
  pasa a `RN-EMB-*` y Documento de vigencia a `RN-VIG-*`, con sus citas.
  `authorization.md` suma los 7 roles sembrados que faltaban; `devops.md`
  lista los 9 jobs del CI y cuáles 6 exige el ruleset; `frontend-architecture`
  trae el mapa de rutas y la app `storefront/`; el índice de deuda del
  ROADMAP se recontó y el primer despliegue de staging figura cerrado.
