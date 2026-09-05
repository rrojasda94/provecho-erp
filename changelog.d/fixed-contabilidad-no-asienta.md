- **El balance estaba vacío y la comida de personal no costaba nada**
  (2026-09-05, ADR-089). No faltaba cableado: el asiento de la venta se genera
  al confirmar la orden —del comprobante aceptado por SUNAT cuelga solo el
  IGV, así que la facturación en pruebas no tiene nada que ver— y el de la
  comida de personal existe desde ADR-034. Lo que fallaba es que el asiento
  **se descartaba en silencio** por dos cosas que había que hacer a mano y
  nadie sabía que existían: importar el plan de cuentas y abrir el periodo del
  mes. Ahora una empresa **nace con su PCGE** (`accounting` escucha
  `organizacion.empresa_creada`) y **el periodo se abre al primer asiento del
  mes** — antes, un mes que nadie abría descartaba todos los asientos
  automáticos del ERP entero, de todos los módulos, sin bloquear nada y sin
  avisar. RN-CTB-010 sigue protegiendo lo que protegía: un mes **cerrado**
  rechaza igual; un mes que nunca se abrió no está cerrado, no existe.
- **La omisión de un asiento deja rastro** (2026-09-05). El único aviso era un
  `log.info` que decía siempre «sin regla_asiento configurada», mentira en
  cuatro de los cinco casos en que el asiento sale vacío, así que quien
  buscaba por qué el balance no cerraba iba a mirar justo donde no estaba el
  problema. La tabla `asiento_omitido` guarda empresa, evento, referencia,
  fecha y motivo —`periodo_cerrado`, `sin_cuentas` con los códigos que faltan,
  `sin_plantilla`—, con su endpoint y un aviso en Contabilidad que dice qué
  hacer con cada uno. Misma forma y misma razón que `incidencia_inventario`.
  Costo aceptado: `duplicado` y `monto_cero` no se anotan —son omisiones
  correctas— y las empresas anteriores al cambio necesitan
  `scripts/sembrar_contabilidad.py`.
- **Cómo registrar la plata que no viene de vender** (2026-09-05): préstamos,
  premios de concurso y mover efectivo del banco a la caja chica se asientan a
  mano, y ahora está escrito con qué cuentas exactas
  (`docs/contabilidad/operaciones-no-operativas.md`). Queda anotado el hueco
  que eso no cierra: el circuito de custodia de ADR-025 cuelga de una apertura
  de caja del PDV, así que el efectivo que sale del banco **no tiene
  responsable nominal** — nadie firma que lo recibió. Es un modelo que falta,
  no un endpoint.
