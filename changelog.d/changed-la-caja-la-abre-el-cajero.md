- **El cajero abre y cierra su caja solo** (2026-08-15, ADR-048, RN-MDP-008,
  migración `c8b41f60d2a7`). `POST /accounting/cajas/apertura` y
  `.../cierre` dejan de exigir la elevación por PIN con
  `accounting.caja_relevar`: alcanza `accounting.caja_operar`, el permiso
  que el rol `cajero` ya tenía. El campo `autorizacion` desaparece de
  `AbrirCajaIn` y `CerrarCajaIn` (era requerido), y
  `AperturaCajaOut.relevo_encargado_id` pasa a nullable.
  El motivo es de operación, no de modelo: para empezar su turno el cajero
  necesitaba que un encargado caminara hasta la caja a poner su PIN, todos
  los días — y eso se pagaba **dejando la sesión del encargado abierta en la
  caja**, que es exactamente el escenario que hace imposible probar quién
  tenía el efectivo. Lo que prueba cuánto había en el cajón sigue siendo el
  conteo por denominación, no una firma.
- **La firma no se debilitó: se movió a donde la plata cambia de manos.** Al
  cerrar, el efectivo queda `en_caja` a nombre del cajero, y el encargado
  firma la recepción después, en `POST /cajas/custodias/{id}/entregar` —
  ahora el único punto del ciclo que pide `accounting.caja_relevar`. Antes
  la custodia nacía directamente en `en_supervisor`: el sistema declaraba
  entregado a las 23:00 lo que se entregaba a las 09:00 del día siguiente, y
  un faltante detectado en el medio le caía al encargado por una firma que
  el software le había puesto solo. El estado `en_caja` ya existía en el
  enum y en la tabla de transiciones desde el primer día — **no lo escribía
  nadie**, así que no hizo falta migrar datos.
  La segregación que importa sigue en pie sin ningún candado nuevo: el
  cajero no puede firmar que recibió su propia plata porque su rol no tiene
  `caja_relevar`.
- **De regalo, recontar un cierre vuelve a significar algo.** Un cierre se
  corrige mientras el efectivo siga en el local (RN-MDP-005); como ahora
  arranca `en_caja` en vez de saltar a `en_supervisor`, recontar *con la
  plata todavía en el cajón* pasó de ser un estado inalcanzable a ser el
  caso normal.
- **Costo aceptado**: `accounting.queries_publicas.encargado_de_turno` salía
  del `relevo_encargado_id` de la caja abierta y devuelve `None` para toda
  apertura nueva, así que `reports` cae en su respaldo por rol
  (`supervisor`/`admin` de la sucursal). Los avisos siguen llegando, a más
  gente y menos dirigidos. Saber quién está a cargo del local necesita una
  fuente propia —un turno de personal— y queda anotado como deuda junto con
  otros dos huecos de permisos que el recorrido de uso destapó: el encargado
  no puede abrir la pantalla donde firma la recepción, y el cajero no ve los
  terminales que RN-POS-010 le pide verificar al abrir.
