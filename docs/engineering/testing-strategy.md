# Estrategia de pruebas

Qué se prueba, en qué nivel, y por qué ese nivel y no otro. Existe para
decidir **antes de escribir** una prueba: la sesión del 2026-08-05 gastó
horas peleando con el arranque de un e2e que, mirado después, cubría cosas
que un test de contrato hubiera cazado en segundos.

## La regla de decisión

Antes de escribir una prueba, una pregunta: **¿qué error real atrapa, y
cuál es el nivel más barato que lo atrapa?**

Si la respuesta al segundo es "uno más barato", ese es el nivel. Un e2e que
prueba una regla de negocio es un test de dominio caro, lento y frágil
disfrazado.

| Nivel | Qué atrapa | Costo | Cuándo |
|---|---|---|---|
| **Dominio** (`tests/test_*.py` sin HTTP) | Reglas de negocio: FEFO, cuadre de caja, aritmética de recetas | ms | Siempre que la regla exista. Es el nivel por defecto |
| **API** (`TestClient`, `tests/test_*.py`) | Contrato HTTP: códigos, permisos, validación, forma del JSON | ms | Todo endpoint nuevo |
| **Contrato cliente↔servidor** | Que el frontend mande y lea **lo que el servidor espera y devuelve** | ms | Ver abajo — es el hueco real |
| **Unidad de frontend** (`node --test`) | Lógica pura del cliente: CSV, orden de tarjetas, avance de KDS | ms | Cuando hay lógica, no marcado |
| **e2e** (Playwright, `frontend/e2e/`) | Que las piezas **arranquen y se hablen**: sesión, navegación, un flujo completo | minutos | Poquísimos, y solo del camino del dinero |
| **Uso** (Playwright, `frontend/uso/`) | Que un recorrido completo **se pueda hacer**, y cómo se ve mientras se hace | minutos | Cuando el entregable son las capturas. No bloquea merge (ADR-047) |

## El hueco real no era e2e

Los dos bugs que motivaron esta estrategia fueron **desacuerdos de
contrato**, no de comportamiento:

- La apertura de caja del PDV mandaba `monto_apertura` cuando el servidor
  ya esperaba `monto_declarado` (ADR-025). Respuesta: 422.
- `GET /ventas` pasó a devolver `{items, total, …}` (ADR-026) y
  `lib/pdv.ts` lo seguía leyendo como array.

Ninguno necesitaba un navegador. Los dos se cazan comparando lo que el
cliente manda contra `docs/architecture/openapi.json`, que **ya se genera y
ya se verifica en CI**.

✅ **Escrito el 2026-08-06** (`frontend/lib/contrato.test.ts`, **186 casos en
menos de un segundo**). Son **dos capas**, y la primera importa más que la
segunda:

**1. El tipo, que es el que trabaja todo el día.** Los cinco cuerpos de
request del PDV viajaban como `Record<string, unknown>` — sin contrato del
lado del cliente, que es por donde entró el bug de ADR-025. Tipados desde
`openapi.json`, `tsc` los verifica **en cada punto de llamada** y ya corre
en CI. Tiparlos destapó cinco desacuerdos el primer día, entre ellos que
`PosVerificado` (lo que se lee, con `serie`) no es `PosVerificadoIn` (lo que
se manda), y dos enums que viajaban como `string` suelto.

**2. El test, que verifica que esos tipos y el contrato digan lo mismo.**
Cubre en **dos profundidades**, y la diferencia importa:

- **Los cuatro módulos importables** (`pdv` 22 operaciones, `catalogo` 25,
  `kds` 7, `reportes` 6) exponen la API como un objeto llamable, así que se
  ejercitan de verdad con `fetch` intervenido: ruta, método, cuerpo contra
  su `requestBody`, y —alimentando al cliente con una respuesta **generada
  desde el contrato**— que la sepa leer. Esto último es lo que caza ADR-026.
  Un `204` se responde vacío de verdad, que es la rama de `pedir` que existe
  porque pedirle `.json()` a una respuesta sin cuerpo revienta.
  Cada lista se compara contra el objeto real del módulo: **una operación
  nueva sin caso hace fallar el test**, no queda sin cubrir en silencio.
- **Todo el resto del frontend** llama desde Server Components y Server
  Actions, que piden `next/headers` y un request y no se pueden importar en
  un `node --test`. Para esos hay un **escaneo del código fuente**: toda
  ruta que el frontend nombra tiene que existir en el contrato con ese
  método. Son ~170 llamadas de Compras, Inventario, RRHH, Gerencia,
  Contabilidad, Marketing y Usuarios. Caza la clase de error que antes no
  cazaba nada: un endpoint renombrado en el backend rompe veinte pantallas y
  el diff de `openapi.json` no sabe quién lo llamaba. **No** valida el
  cuerpo que esas pantallas arman — eso sigue siendo trabajo de `tsc` sobre
  tipos escritos a mano.

El validador cubre a propósito solo lo que se rompe en silencio: requerido
que no viaja, campo que el contrato no conoce, tipo equivocado. `pattern`,
`minimum` y enums los rechaza el servidor con un 422 que **se ve**;
replicarlos acá sería mantener dos validadores desincronizándose.

Verificado por mutación, que es lo único que prueba que un test verde pueda
ponerse rojo. Cinco mutaciones, cinco rojos: los dos bugs históricos, un
endpoint renombrado en `lib/`, otro renombrado en un Server Action, y una
operación nueva sin caso de contrato. Más un piso (`> 150 llamadas`) para
que el escaneo no pase por vacío si alguien cambia cómo se llama a la API.

## Qué sí justifica un e2e

Tres cosas, y ninguna es una regla de negocio. **Las tres están cubiertas**
(2026-08-06) — la lista es también el techo: lo que no entra acá no se
escribe como e2e.

1. **Que la sesión funcione**: login → cookie httpOnly → una pantalla
   protegida. Si esto se rompe, no importa qué más ande.
   `e2e/sesion.spec.ts`. El atributo `httpOnly` se afirma explícitamente: no
   se ve en ninguna pantalla, así que se rompe en silencio, y un token
   legible por `document.cookie` lo roba cualquier XSS.
2. **Un solo flujo del dinero completo**: abrir caja → vender → cobrar →
   cerrar. No para verificar el descuadre —eso es dominio— sino para
   verificar que las cuatro pantallas encadenan. `e2e/caja.spec.ts`.
3. **Los candados que solo existen en pantalla**: el diálogo bloqueante de
   apertura (sin caja no se vende), que un rechazo del servidor deje el
   formulario abierto con lo tecleado en vez de perderlo, y el **gate de
   módulo por permiso** (ADR-013 + enmienda 2026-08-03) probado **entrando
   por URL directa** — el filtro del home es UX, lo que decide es el
   `layout.tsx`, y solo la URL directa distingue uno del otro.

Un gate se prueba **de a pares**: el cajero no ve Catálogo *y* el admin sí.
Sin la contraparte, un gate que esconde el módulo para todos pasa por bueno.

Todo lo demás que se sienta como "hay que probar la pantalla" es, casi
siempre, un test de contrato o de dominio mal ubicado.

### Enmienda 2026-08-15 (ADR-047): el techo sigue, pero ya hay adónde mandar el resto

El techo **no se levanta**: `frontend/e2e/` sigue cubriendo esas tres cosas y
nada más. La razón por la que existe no cambió — es un check requerido, corre
con un solo worker, y cada caso nuevo es tiempo que paga todo merge del repo,
incluido el arreglo urgente que no toca ninguna pantalla.

El techo es de **categorías, no de casos**: hoy son 16 casos en cuatro
archivos y los 16 caen en las tres de arriba —el guard del lienzo, el bloqueo
de pantalla y el login sin campo de contraseña (ADR-050) son "candados que
solo existen en pantalla": del lado del servidor no hay ninguna diferencia
entre un PIN escrito y uno tocado—. Una cuarta categoría es lo que no entra.

Lo que cambia es la salida para lo que no entra. Antes había dos: agregarlo
igual (y romper el techo) o no escribirlo. Ahora hay una tercera, `uso/`, con
otro propósito y otras consecuencias.

## La suite de uso (`frontend/uso/`)

Responde otra pregunta. `e2e` pregunta *¿arranca y se hablan?*; `uso`
pregunta *¿esto se puede usar de punta a punta?* — y su entregable **no es el
verde, son las capturas**. Es lo que permite mirar una pantalla sin instalar
el ERP, y dejar evidencia de cómo se veía.

|  | `e2e/` | `uso/` |
|---|---|---|
| Techo | las tres cosas de arriba | no tiene |
| `screenshot` / `trace` | `on-failure` | `on` |
| Reintentos en CI | 1 | 0 |
| Check requerido | **sí** | **no** |
| Artefacto en CI | `if: failure()` | `if: always()` |

```bash
npm run test:uso        # frontend/, mismo seeder y misma base que test:e2e
```

Reglas propias, además de todas las de abajo (que siguen valiendo igual):

- **Captura en cada hito**, con `capturar(page, testInfo, "<nombre>")`
  (`uso/util.ts`). Se numeran solas: la carpeta se lee como una secuencia.
- **No bloquea un merge, y no debe empezar a hacerlo.** El job `uso` de
  `ci.yml` está fuera de los seis requeridos y además con
  `continue-on-error: true`. Un recorrido largo se cae por cosas que no son
  bugs, y un check requerido que falla por ruido es un check que la gente
  aprende a ignorar. Agregarlo al ruleset es cambiar la decisión de ADR-047,
  no corregir un olvido.
- **Las capturas nunca se versionan.** Van a `frontend/test-results/uso/`,
  que ya está en `.gitignore`, y CI las sube como artefacto.
- El arranque de los dos servidores es el mismo que el de `e2e` y vive en
  `frontend/playwright.comun.ts`. Si hay que tocar puertos o tiempos, se
  tocan ahí una vez.

## Reglas para escribir un e2e (o un recorrido de uso)

Aprendidas a los golpes; cada una costó tiempo. Valen igual para las dos
suites: comparten el arranque, la base y el seeder.

- **Los datos los siembra un seeder versionado** (`src/seeders/e2e.py`), no
  el test. Un test que crea sus datos por la UI prueba tres flujos para
  verificar uno. Lo que ya está sembrado —y por lo tanto **no hay que volver
  a sembrar**— es:

  | Para probar | Ya existe |
  |---|---|
  | Caja y venta simple | punto de venta y POS por sucursal, `admin`, `encargado_e2e`, `cajero_e2e`, medio de pago |
  | Venta de un producto plano | `Pizza E2E` (S/ 25.00), un solo insumo, con stock |
  | Variantes, grupo obligatorio y extras | `Menú E2E` → Simple/Doble → grupo `Guarnición` (`minimo=1`) → `Extra Queso E2E` |
  | Inventario | cuatro insumos con SKU y stock en el almacén central |
  | Compras | proveedor `Distribuidora E2E SAC` y una orden de compra **en borrador** |

  La orden queda en borrador a propósito: emitirla es el paso que un
  recorrido quiere dar **por la pantalla**, y una orden que llega emitida se
  lo saltea. Si una rama necesita algo que no está, se agrega **al seeder**,
  no al test — y se agrega sin tocar `Pizza E2E`, que es plana a propósito
  (las pruebas del lienzo dependen de que tenga un único insumo).
- **Base desechable y rehecha en cada corrida.** Los seeders son
  idempotentes pero el *estado* no: una corrida que deja la caja abierta
  hace fallar a la siguiente con un mensaje que no menciona la corrida
  anterior.
- **Nunca reusar servidores** entre corridas, y **fijar la configuración
  dentro del proceso que la usa**: pasarla por capas (npm → next) falla en
  silencio y el síntoma aparece a tres pasos de la causa.
- **Esperar contenido, no navegación.** El `redirect` de una Server Action
  lo resuelve el cliente y no dispara `load`.
- **Acotar los selectores al contenedor visible.** Varios diálogos conviven
  montados en el DOM y comparten `data-testid`.
- **Un `data-testid` es una decisión de diseño, no un parche**: se agrega
  donde el texto visible es ambiguo o cambia con el idioma, no en todos
  lados.
- **La prueba pasa por los candados, no los rodea.** Si la pantalla exige un
  paso antes de cobrar, el test lo da: saltárselo no prueba el flujo del
  cajero, prueba uno que no existe.
- **Presupuesto de tiempo generoso en modo desarrollo.** `next dev` compila
  cada ruta la primera vez que se la pide. Un timeout corto no falla donde
  está el problema: falla donde se acabó el reloj, y como cada corrida deja
  la caché más tibia, el punto de falla se mueve solo. Eso se lee como
  flakiness y no lo es.

## Estado actual (2026-08-15)

Números contados, no recordados: `pytest --collect-only -q`, `npm test`, y
los `test(` de `frontend/e2e/`. Los anteriores (895 / 183 / 7) eran del
2026-08-06 y llevaban nueve días vencidos, que es lo que pasa con un conteo
escrito a mano: envejece sin avisar.

- Dominio y API: **1379 casos** en verde, en CI. Salen de **1041 funciones
  `test_*`** repartidas en **76 archivos** de `tests/`; la diferencia son
  `parametrize`.
- Unidad de frontend + contrato: **258 casos** (`npm test`), en CI desde
  2026-08-06 — el job de frontend hacía solo `lint` y `build`. De esos, **186
  son de contrato** (`lib/contrato.test.ts`) y 7 (2026-08-07,
  `lib/carga.test.ts`) cubren la clasificación de fallos de carga: que una red
  caída no se confunda con un 403 ni se dibuje como lista vacía.
- e2e: **16 casos en verde y en CI** (job `e2e`), sobre PDV, sesión, el gate
  de módulo, el lienzo de nodos, el bloqueo de pantalla y el login con pinpad
  (ADR-050). Los tres puntos de "qué sí justifica un e2e" quedan cubiertos.
  Ver ROADMAP → Frontend.
- Uso: **1 caso** (`uso/humo.spec.ts`), que prueba el arnés y no una pantalla.
  Job `uso`, **no requerido** (ADR-047).

Los cuatro niveles de la tabla existen y ninguno está vacío. Lo que queda
abierto, dicho sin adornos: **el cuerpo que arman las pantallas de Compras,
Inventario, RRHH, Gerencia, Contabilidad, Marketing y Usuarios no está
verificado contra el contrato** — de esas solo se comprueba la ruta. Se
cerraría moviendo sus llamadas a módulos importables como los cuatro que ya
lo son, no escribiendo otro tipo de test.

## Nota de velocidad

Desde **2026-08-08** la base de desarrollo es el contenedor `db` del
docker-compose, en la máquina. Antes vivía en Supabase y cada consulta
costaba ~130 ms de ida y vuelta: lo pagaba toda prueba que pasara por HTTP
y también las pantallas, que se sentían lentas en desarrollo. En local esa
latencia baja al orden del milisegundo.

Las pruebas automatizadas siguen usando SQLite en memoria o un archivo
desechable: no dependen de que Postgres esté levantado. El cambio le pega
sobre todo a e2e y al trabajo manual contra la API.
