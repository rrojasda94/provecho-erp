# Google Maps: direcciones ancladas y distancia de reparto

Provecho usa Google en dos lugares y por dos motivos distintos:

| Uso | Dónde corre | API | Clave |
|---|---|---|---|
| Autocompletar la dirección y ubicarla en un mapa | navegador | Maps JavaScript, Places (New), Geocoding | `GOOGLE_MAPS_BROWSER_KEY` |
| Medir la distancia con la que se cobra el delivery | servidor | Routes | `GOOGLE_MAPS_SERVER_KEY` |

**Son dos claves y no una** porque Google no permite restringir la misma clave
por referente HTTP *y* por dirección IP a la vez. Y son dos riesgos distintos:
la del navegador se puede leer desde el código de la página —sirve para dibujar
un mapa y nada más—, mientras que la del servidor decide cuánta plata paga el
cliente y no puede salir de la API.

El porqué de cada decisión está en ADR-053 (la dirección se elige en el mapa) y
ADR-054 (el delivery se cobra por kilómetro). Este documento es el
procedimiento: qué se clickea, en qué orden y qué se verifica.

## Requisito previo

Una cuenta de Google Cloud con **facturación activa**. Las APIs de Maps
responden `REQUEST_DENIED` sin cuenta de facturación vinculada, aunque la clave
sea correcta y el crédito gratuito esté disponible.

## 1. Proyecto

1. <https://console.cloud.google.com> → selector de proyecto (arriba a la
   izquierda) → **Proyecto nuevo**.
2. Nombre `provecho-erp`. Dejarlo seleccionado para todo lo que sigue.
3. Menú ☰ → **Facturación** → *Vincular una cuenta de facturación* → elegir la
   cuenta existente.

## 2. Habilitar las APIs

☰ → **APIs y servicios** → **Biblioteca**, y habilitar una por una:

- **Maps JavaScript API** — el mapa embebido.
- **Places API (New)** — el autocompletado y el detalle del lugar (place_id,
  coordenadas, plus code, distrito).
- **Geocoding API** — traducir coordenadas a dirección cuando se arrastra el pin.
- **Routes API** — la distancia de reparto (`computeRouteMatrix`).

> La *Distance Matrix API* clásica hace lo mismo que Routes y sigue
> funcionando, pero Google la tiene marcada como legada. Se habilita **Routes**
> y no aquella. Confirmar precio y nombre exacto en
> <https://developers.google.com/maps/billing-and-pricing/pricing> antes de
> activar: el catálogo de Maps se renombra seguido.

## 3. Clave del navegador (`provecho-web`)

1. **APIs y servicios** → **Credenciales** → *Crear credenciales* → *Clave de
   API*. Renombrarla `provecho-web`.
2. *Editar clave* → **Restricciones de aplicación** → **Sitios web (referentes
   HTTP)**, y agregar:
   - `http://localhost:3000/*`
   - `https://<dominio-de-produccion>/*`
3. **Restricciones de API** → *Restringir clave* → marcar **solo** Maps
   JavaScript API, Places API (New) y Geocoding API.
4. Guardar. Los cambios tardan hasta 5 minutos en propagarse: una clave recién
   restringida puede fallar un rato y no está rota.

Esta clave llega al navegador. Está bien: es su función. Lo que la protege es
la restricción por dominio y la cuota diaria del paso 5, no el secreto.

## 4. Clave del servidor (`provecho-servidor`)

1. Crear una **segunda** clave, `provecho-servidor`.
2. **Restricciones de aplicación** → **Direcciones IP** → la IP pública del VPS
   donde corre la API (y la del entorno de pruebas, si aplica).
3. **Restricciones de API** → *Restringir clave* → **solo Routes API**.

Esta clave nunca se pasa al contenedor `web` (ver *Variables de entorno*).

## 5. Techo de gasto

Sin esto, una clave filtrada es una factura abierta.

1. Por cada API habilitada: **APIs y servicios** → la API → pestaña **Cuotas** →
   fijar un límite diario de solicitudes. 1000/día es un punto de partida
   razonable para un grupo de cuatro locales; se sube cuando el uso real lo
   pida.
2. **Facturación** → **Presupuestos y alertas** → presupuesto mensual (p. ej.
   USD 30) con avisos al 50 %, 90 % y 100 % al correo del administrador.

## 6. Variables de entorno

Las claves se pegan en el `.env` del servidor —nunca en el repositorio— y se
reparten así:

| Variable | `api` / `worker` | `web` |
|---|---|---|
| `GOOGLE_MAPS_BROWSER_KEY` | — | sí |
| `GOOGLE_MAPS_SERVER_KEY` | sí | **no** |

`api` y `worker` leen `.env` completo (`env_file:` en el `docker-compose.yml`).
El servicio `web` no: recibe solo la variable que se le declara explícitamente,
y por eso la clave del servidor no llega ahí.

**Dos formas de tener la clave puesta y que no sirva de nada**, las dos
encontradas el 2026-08-25 y las dos corregidas:

- **Con el nombre viejo.** `.env.staging.example` traía un `GOOGLE_API_KEY=`
  que **ningún código lee** —quedó de una integración que nunca se escribió—.
  Los nombres que se buscan son exactamente `GOOGLE_MAPS_BROWSER_KEY` y
  `GOOGLE_MAPS_SERVER_KEY`. Una clave con el nombre viejo no enciende nada y
  no hay error que lo avise.
- **En el `.env` correcto pero sin llegar al contenedor.**
  `docker-compose.staging.yml` y `docker-compose.prod.yml` **no le pasaban
  ninguna** `GOOGLE_MAPS_*` al servicio `web`: el `.env` del servidor podía
  tenerla y el proceso de Next no la veía. Solo el compose de desarrollo la
  declaraba.

Por eso la comprobación que vale es la de `/gerencia/delivery` (ADR-066) y no
mirar el `.env`: la pantalla dice lo que el **proceso** tiene, no lo que el
archivo dice.

**No es `NEXT_PUBLIC_*`.** Esa familia de variables se hornea en el build de
Next.js —la misma razón por la que se eliminó `NEXT_PUBLIC_API_URL`, ver
[devops.md](devops.md#docker)—. La clave la lee un Server Component en tiempo de
ejecución y baja al componente del mapa como prop.

Resto de la configuración (`GOOGLE_ROUTES_BASE_URL`, `GOOGLE_TIMEOUT_SEGUNDOS`,
`GOOGLE_MAPS_PAIS` y el bloque `DELIVERY_*`) está documentada línea por línea en
`.env.example`. Los `DELIVERY_*` son solo la **semilla**: la tarifa que se
cobra la fija Gerencia en `/gerencia/delivery` y vive en la base (ADR-066).

**Fuera de Docker** (`npm run dev` en `frontend/`) el `.env` de la raíz no se
lee: hay que copiar `frontend/.env.example` a `frontend/.env.local`. Sin eso
el campo de dirección se ve como un cuadro de texto y parece que la
integración no existe.

**En staging** las mismas variables van en el `.env` del droplet — ver
`.env.staging.example`. La clave del navegador se restringe al **dominio de
staging**, no a `localhost`: una clave restringida al dominio equivocado se
comporta igual que una clave ausente, y el SDK falla en silencio.

## 7. Qué pasa si falta cada clave

Ninguna de las dos es obligatoria para que el ERP funcione. Es a propósito: una
integración con un tercero no puede impedir dar de alta un proveedor ni cobrar
un pedido (mismo criterio que ADR-005 y ADR-041).

- **Sin `GOOGLE_MAPS_BROWSER_KEY`**: el campo de dirección es el cuadro de texto
  de siempre. Se escribe a mano, se guarda, no hay coordenadas. Es también lo
  que ocurre en el hub offline de una sucursal sin internet.
- **Sin `GOOGLE_MAPS_SERVER_KEY`**: la distancia se estima en línea recta y la
  cotización se marca *aproximada*. El pedido se toma igual.
- **Con las dos vacías**: el sistema se comporta exactamente como antes de esta
  integración.

Esa degradación silenciosa es correcta frente al cajero —una venta no se
pierde porque un tercero no contestó— y engañosa frente a Gerencia: parece que
la función nunca se construyó. Por eso **`/gerencia/delivery` dice cuál de las
dos claves falta** (ADR-066). Ante un «el mapa no aparece» o «las rutas no
están», esa pantalla es el primer lugar donde mirar, antes que el `.env`.

## 8. Verificar que quedó bien

1. `docker compose up` y abrir *Organización → Sucursales* → editar una.
2. Escribir tres letras de una calle: tienen que aparecer sugerencias.
3. Elegir una: el mapa centra el pin y la ficha guarda coordenadas.
4. **Consola del navegador sin violaciones de CSP.** Es el fallo más común al
   configurar esto y no se ve de otra forma.
5. Pestaña *Red* del navegador: **no puede** haber ninguna llamada a
   `routes.googleapis.com`. Si aparece, la distancia se está calculando en el
   cliente y el cobro del delivery es manipulable.
6. En Google Cloud, *APIs y servicios* → *Panel*: el tráfico tiene que
   aparecer en las APIs esperadas y en ninguna otra.
7. *Gerencia → Delivery*: los tres renglones de arriba tienen que estar en
   verde. Es la comprobación que no exige abrir la consola de Google ni el
   `.env` del servidor, y la única que puede hacer alguien que no es de
   sistemas.
8. Con la tarifa aprobada, tomar un delivery en el PDV con dirección anclada:
   los kilómetros tienen que salir **sin** «aprox.» (prueba de que Routes
   contestó) y el ticket tiene que mostrar la fila *Reparto*.

## Rotación

Igual que el resto de los tokens de integraciones
([devops.md](devops.md#rotación-de-credenciales)): revocar primero en Google
—*Credenciales* → borrar la clave— y después actualizar `.env` y reiniciar. Una
clave que llegó a un commit se considera quemada.

La del navegador viaja al cliente por diseño, así que "filtrada" no es motivo de
rotación por sí solo; lo que se revisa ante un pico de uso es que las
restricciones de dominio y las cuotas sigan puestas.
