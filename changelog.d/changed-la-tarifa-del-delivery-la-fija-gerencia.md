- **El delivery por kilómetro estaba construido y nadie podía usarlo**
  (2026-08-25, ADR-066, RN-COM-040, sin migración). Tres meses después de
  mergear ADR-053/054 la respuesta del negocio seguía siendo «eso no está
  disponible», y ninguna de las tres causas era de dominio: **la tarifa vivía
  en el `.env`**, así que cambiarla exigía editar el servidor y redesplegar —
  motivo por el cual los tres valores nunca salieron de `0` y la función
  quedó apagada desde el día uno—; **el reparto se calculaba, se congelaba en
  `venta.costo_entrega` y no se cobraba**, que desde caja se lee como que el
  PDV está roto (el cajero ve «reparto S/ 5» y el ticket cobra S/ 0); y **sin
  claves de Google todo se degrada en silencio**, que frente al cajero es lo
  correcto —una venta no se pierde porque un tercero no contestó— y frente a
  Gerencia es una pantalla que parece andar y no anda.
- **La tarifa la fija Gerencia, no un archivo del servidor.** Los cuatro
  números pasan a ser `parametro_empresa` del módulo `sales`
  (`delivery_tarifa_base`, `delivery_precio_por_km`, `delivery_radio_km`,
  `delivery_distritos_restringidos`) y se editan en la sección nueva
  **`/gerencia/delivery`**. `settings.delivery_*` queda como **semilla**: el
  valor con el que cotiza una empresa que todavía no aprobó ninguno, así que
  el día del despliegue no cambia de precio ni una venta. Como cualquier
  parámetro de ADR-014, **el valor nuevo no cobra hasta que Gerencia lo
  aprueba** (RN-GER-009) — acá se define cuánta plata paga el cliente, y el
  mismo mecanismo que audita el umbral de una orden de compra vale para esto.
  Un parámetro mal formado cobra la semilla en vez de reventar: es un JSON que
  pasó por un formulario, y un 500 en caja es peor que cobrar el precio
  anterior.
- **El reparto entra al total de la venta** (RN-COM-040). Se suma **después**
  del descuento manual —el encargado autoriza descontar lo que el cliente
  consumió, no el flete—, **un consumo de personal no lo paga** (vale cero
  entero, RN-COM-025) y **no se prorratea entre cuentas separadas**: va entero
  en la primera cuenta, porque una mesa dividida no es un delivery pero la
  suma de las cuentas sí tiene que dar el total de la venta. Sin línea de venta, contra lo que ADR-054 dejó
  anotado: crear un producto de servicio «Delivery» con su receta, su
  categoría y su cuenta contable para mover un número que ya tiene su columna
  no compra nada hoy, y `costo_entrega` sobrevive al comprobante igual. El
  ticket del PDV muestra el reparto en su propia fila. El PDV además pasa a
  cotizar **aunque la dirección no tenga ancla en el mapa**: hasta ahora no se
  pedía porque no había nada que medir, y desde que el flete se cobra eso
  dejaba al cajero diciéndole al cliente un total menor que el cobrado — que
  es el caso normal mientras no haya clave de Maps, no el raro. Esa llamada no
  toca a Google: sin destino, la cotización devuelve la tarifa base y no
  pregunta.
- **La pantalla de Gerencia dice qué falta.** `GET
  /sales/delivery/configuracion` devuelve la tarifa **efectiva** —lo aprobado,
  o la semilla— y no lo propuesto, más `activa` y `rutas_reales`: la sección
  avisa si el reparto no se está cobrando, si falta `GOOGLE_MAPS_SERVER_KEY`
  (toda distancia sale de la línea recta y se cobra «aprox.») y si falta
  `GOOGLE_MAPS_BROWSER_KEY` (no hay buscador ni pin, y sin punto no hay
  distancia que medir). Es la comprobación que puede hacer alguien que no es
  de sistemas, sin abrir la consola de Google ni el `.env` del servidor.
- **La clave del mapa no llegaba al frontend fuera de desarrollo**, y ese era
  el otro motivo real del «no está disponible». `docker-compose.staging.yml` y
  `docker-compose.prod.yml` **no le declaraban ninguna `GOOGLE_MAPS_*` al
  servicio `web`**: solo el compose de desarrollo lo hacía, así que el `.env`
  del servidor podía tener la clave correcta y el proceso de Next no verla
  nunca — sin buscador, sin mapa y, por lo tanto, sin punto que medir para
  cobrar el reparto. Se declaran ahora en los tres, igual que en desarrollo, y
  la del servidor sigue sin pasar al `web` (llega por `env_file: .env` al
  `api`, que es la separación de ADR-054).
- **Y la plantilla de staging invitaba a ponerla con el nombre equivocado**:
  `.env.staging.example` traía `GOOGLE_API_KEY=`, que **ningún código lee**,
  y ninguna de las `GOOGLE_MAPS_*` que sí se leen. Ahora están las cuatro, con
  el nombre viejo marcado como muerto. Se suma `frontend/.env.example`, que no
  existía: quien corre `npm run dev` fuera de Docker no tenía forma de
  enterarse de que el campo de dirección necesita una clave para ser algo más
  que un cuadro de texto.
