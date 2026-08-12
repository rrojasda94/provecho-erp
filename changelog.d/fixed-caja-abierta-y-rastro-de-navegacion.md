- **El PDV pedía abrir una caja que ya estaba abierta** (2026-08-12). El
  cajero entraba, le aparecía el diálogo de apertura, y al aceptarlo el
  servidor lo rechazaba —correctamente— con "ya hay una caja abierta": un
  callejón sin salida donde no se puede ni vender ni entender por qué.
  El origen era un permiso mal elegido: `GET /accounting/cajas/abiertas`
  exigía `accounting.leer`, que es el permiso de **todo** el módulo contable y
  que el rol `cajero` no tiene ni le corresponde. Recibía 403 y el PDV lo
  trataba como "no hay caja". Ahora el endpoint acepta `sucursal_id` y en ese
  caso alcanza con `accounting.caja_operar` —quien opera una caja puede
  preguntar si su turno está abierto— con el alcance validado contra el tenant
  (ADR-004), no contra el parámetro. Sin `sucursal_id` sigue siendo la empresa
  entera y sigue exigiendo `accounting.leer`: quien opera una caja no tiene por
  qué ver el efectivo de los demás locales. La caja es del **punto de venta**,
  así que el turno que abrió un compañero vale para todos los del local.
- **Un fallo al consultar la caja ya no se dibuja como "no hay caja"**: el
  `.catch(() => setCaja(null))` del PDV era el mismo patrón que `useLista` ya
  había corregido en el resto de sus cargas. Ahora la pantalla dice qué pasó y
  no ofrece abrir una caja sobre la que no pudo preguntar.
- **El "volver" de las fichas subía de nivel en vez de volver** (ADR-039).
  Llegando a una receta desde la ficha de un producto, `← Recetas` llevaba al
  listado y no al producto. Cada ficha cableaba su propia salida —nueve en
  total— y todas contestaban "¿qué hay encima?" cuando la pregunta era "¿de
  dónde vengo?". Ahora hay un `<Rastro>` con dos controles: el rastro
  jerárquico (Inicio / Módulo / Sección / lo que se ve), derivado de la ruta
  contra los mismos registros que alimentan el sidebar y la paleta, y un `←`
  que usa el historial propio y cae al padre cuando no lo hay —una entrada por
  URL directa o una recarga—.
