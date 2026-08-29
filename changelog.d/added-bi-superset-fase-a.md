- **Capa semántica para un BI autoservicio con Apache Superset** (ADR-082,
  Fase A; RN-BI-001..004). El dashboard actual (ADR-024) no permite elegir
  libremente eje X/eje Y/valores, cruzar dimensiones ni más tipos de gráfico
  que barras/líneas/tabla — y ADR-024 rechazó a propósito construir eso
  dentro de Provecho, dejando escrito que la salida era exportar a una
  herramienta de BI con su propio control de acceso. Esta entrega es esa
  salida: diez vistas `vw_bi_*` (ventas, pagos, inventario, stock, compras,
  contabilidad, caja, producción, asistencia de RRHH, encuestas) más
  `bi_alcance_usuario`, y un rol de Postgres (`bi_lector`) con `GRANT
  SELECT` únicamente sobre esas vistas — no ve `usuario`, `boleta_pago` ni
  ninguna tabla base. `production`, `rrhh` (más allá de nombre y cargo) y
  `marketing` quedan analizables sin sumar veinte entradas al catálogo
  cerrado de `core/reportes`, que no se toca.
- **El costo que se acepta, y va probado**: ADR-004 filtra tenant en la
  aplicación, no con RLS de Postgres, así que el BI necesita su propio punto
  de aplicación (`bi_alcance_usuario`, que la RLS de Superset consultará en
  la Fase C). Si ese punto diverge de `Tenant.sucursal_ids`, alguien ve una
  sucursal que no debería — `tests/test_bi_alcance.py` compara los dos
  contra Postgres real (corre en el job `migraciones` de CI, no en el suite
  de SQLite) y es la única razón por la que esa fuga no puede pasar
  desapercibida.
- **De paso, un full-scan que el BI habría hecho notar tarde o temprano**:
  `contar_bajo_minimo` traía toda la tabla `stock` de la empresa a Python
  para contarla en un bucle, en el engine corto del dashboard. Ahora es un
  `COUNT` agregado en SQL.
- Pendiente en próximas entregas (ver ADR-082 y ROADMAP → Deuda técnica):
  Provecho como proveedor OAuth2 para el SSO de Superset, el despliegue de
  Superset con su RLS, la integración/embebido en `/dashboard`, y la
  exportación (print, XLSX completo, PDF).
