- **Producción no verificaba la inocuidad de turno antes de operar**
  (2026-09-09, bloque `feat/produccion-checklist-inocuidad` del plan de
  deuda de producción, RN-CDP-002/005). Nueva tabla
  `checklist_inocuidad_turno`: bioseguridad, superficies, limpieza
  intermedia, equipos de frío (JSONB `[{equipo, temperatura_c, rango_min,
  rango_max, dentro_rango}]` — `dentro_rango` lo calcula el servidor, nunca
  el cliente) e indicio de plaga; único por `almacen_id, fecha, turno`.
  `POST /production/checklists` calcula `estado` (`aprobado`|`bloqueado`):
  cualquier falla bloquea la cocina entera, no solo el equipo puntual (más
  estricto que la letra de RN-CDP-005, mismo criterio que el resto del
  modelo de datos y el SOP de inocuidad). Sin un checklist `aprobado`
  vigente del día en un almacén `tipo=produccion`, `crear_orden_produccion`
  y `registrar_consumo` rechazan con 409 `cocina_bloqueada`. Publica
  `production.equipo_frio_fuera_rango` (por cada equipo fuera de rango) y
  `production.cocina_bloqueada`, ambos nivel `urgente` en el catálogo de
  `reports` (alerta a Gerencia y Cocina) — el primero estaba documentado en
  `events.md` desde antes pero el código nunca llegó a publicarlo. Nuevo
  permiso `production.verificar_inocuidad` (seeder + `jefe_cocina`) y
  pantalla `/produccion/inocuidad`. Simplificación documentada:
  `orden_produccion` no registra en qué turno se creó, así que "vigente" es
  el checklist más reciente del almacén ese día, sin distinguir turno — una
  vez bloqueada la cocina, sigue bloqueada hasta que un checklist nuevo (de
  cualquier turno) la reapruebe.
