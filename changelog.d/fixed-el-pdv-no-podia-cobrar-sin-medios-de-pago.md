- **El PDV no podía cobrar en un entorno recién levantado.** `seeders.seed`
  no daba de alta **ningún medio de pago** —solo lo hacía `pdv_demo`, y
  `docker-compose.staging.yml` corre únicamente el seeder base—, así que el
  diálogo de cobro no dibujaba ninguna pastilla de medio, no había forma de
  elegirlo, tampoco había vuelto (solo lo da un medio de tipo `efectivo`) y
  «Confirmar pago» mandaba `medio_pago_id: ""`. Lo que el cajero veía era
  `Input should be a valid UUID, invalid length: expected length 32 for
  simple format, found 0`, un error que no se puede entender ni corregir
  desde esa pantalla. Tres cambios:
  - `seeders.seed` siembra Efectivo, Yape y Tarjeta por empresa
    (`direccion="cobro"`), idempotente y por la misma razón que ya sembraba
    `usuario_sucursal`: una instalación nueva tiene que quedar operable.
    `pdv_demo` y `e2e` dejan de duplicarlo.
  - El diálogo de cobro **bloquea** «Agregar» y «Confirmar pago» sin medio
    elegido, y dice que no llegó ninguno en vez de dejar mandar el vacío.
  - La aritmética del cobro sale del JSX a `frontend/lib/cobro.ts`
    (`calcularCobro`, `cobroBloqueado`) con pruebas en `node --test`: el
    vuelto en efectivo, el bloqueo del exceso en un medio sin cajón, el
    segundo medio que cubre el faltante y el medio vacío.
  Pendiente, anotado en `docs/roadmap/deuda/frontend.md`: no existe pantalla
  para dar de alta medios de pago; el alta sigue siendo por API.
