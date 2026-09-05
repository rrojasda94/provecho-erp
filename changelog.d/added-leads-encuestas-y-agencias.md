- **Marketing dejaba tres cosas sin ver, y no era solo falta de pantalla**
  (2026-09-05, Ola 3 de la auditoría del 2026-08-30, migración
  `c7a1e94b2d38`). Faltaban también los **endpoints de listado**:
  - **Leads** (`/marketing/leads`): se listaban solo por campaña, así que la
    pregunta que se hace de verdad —«¿qué pistas quedaron sin trabajar?», que
    cruza campañas— no se podía hacer. Ahora se filtra por campaña y por si el
    lead se convirtió en venta.
  - **Encuestas** (`/marketing/encuestas`): no había listado. Una encuesta
    solo se podía mirar sabiendo su id o el de su venta, así que las
    respuestas quedaban donde nadie las leía — y una encuesta que nadie lee es
    una molestia al cliente sin contrapartida. Se ve el puntaje promedio, el
    comentario y los envíos fallidos, que no son lo mismo que una sin
    contestar.
  - **Evaluación de agencias** (`/marketing/agencias`): se listaban por
    campaña, y quien decide no entra por la campaña sino por la decisión
    pendiente. Se ven las opciones con su puntaje ponderado y cuál ganó.
  `encuesta_satisfaccion` gana **`empresa_id`**: cuelga de una venta que vive
  en `sales`, así que sin esa columna filtrar por tenant era un join entre
  módulos — mismo criterio con el que `postulante` ganó el suyo. La migración
  rellena las filas anteriores por el camino largo (venta → sucursal), que a
  partir de ahora nadie tiene que recorrer.
  Costo aceptado: atribuir un lead a una venta **a mano** sigue por API
  (hace falta un buscador de ventas), y cargar opciones y firmar la decisión
  de agencia también — la decisión la firma Gerencia con motivo obligatorio
  cuando se aparta de la recomendada, y eso es un formulario con reglas
  propias.
