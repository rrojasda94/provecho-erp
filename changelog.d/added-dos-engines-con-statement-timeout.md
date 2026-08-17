- **`statement_timeout`, y son dos** (2026-08-15). `connect_timeout: 5` cubría
  no poder conectar; un Postgres que **acepta la conexión y después se traba**
  —lock ajeno, plan malo, disco al límite— seguía clavando el request sin
  límite, porque `pool_pre_ping` hace un `SELECT 1` al sacar la conexión del
  pool y después no mira más. `src/core/database.py` abre ahora **dos engines**
  contra la misma base: el de operación (`SessionLocal`,
  `DB_STATEMENT_TIMEOUT_SEGUNDOS=15`) es el default de todo el ERP, y el de
  reportes (`SessionReportes`, `DB_STATEMENT_TIMEOUT_REPORTES_SEGUNDOS=120`) lo
  consumen `src/core/reportes/` y el módulo `reports` vía la dependencia
  `get_db_reportes`. Un número único obligaba a elegir entre cancelar reportes
  que estaban trabajando bien o dejar la caja esperando; en el mostrador, un
  error se maneja mejor que una pantalla que no vuelve. Costo aceptado: un
  segundo pool de conexiones — que de paso impide que una consulta pesada de
  reportes se coma las conexiones de la caja. `0` desactiva el límite, y fuera
  de Postgres el parámetro no se pasa (el `e2e` corre sobre SQLite, que no sabe
  cancelar por tiempo). Un test de arquitectura falla si un endpoint queda del
  lado equivocado.
- **Ningún barrido puede abrir la base de producción desde un test**
  (2026-08-15). `inventory/application/tasks.py`, `sales/application/tasks.py`
  y `rrhh/purga.py` llamaban `SessionLocal()` directo: el test que los
  ejercitaba pagaba una conexión real —5 s de `connect_timeout`— o, con la base
  de desarrollo levantada, corría el barrido **contra ella**. Ahora exponen
  `session_factory` como los listeners y entran en el guardián autouse de
  `tests/conftest.py`, que ya cubría a los cinco módulos de listeners.
