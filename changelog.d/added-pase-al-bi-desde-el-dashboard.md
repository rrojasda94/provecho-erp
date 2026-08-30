- **El BI no tenía puerta desde el dashboard** (2026-08-30). El módulo existe,
  el permiso `bi.acceder` existe y su ficha está en el home desde ADR-083, pero
  quien estaba mirando el tablero del día —que es justo quien quiere cruzar
  esos datos a mano— tenía que volver al home y entrar por la otra ficha. Ese
  rodeo no lo hacía nadie, así que el BI quedaba sin usar. Ahora el dashboard
  ofrece el pase, condicionado al permiso. Va en la página y no en el sidebar
  porque `ModuloShell` no filtra los ítems de `SUBMENUS`: ahí se le ofrecería
  también a quien no puede entrar, para mandarlo a un "sin permiso".
