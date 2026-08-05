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
| **e2e** (Playwright) | Que las piezas **arranquen y se hablen**: sesión, navegación, un flujo completo | minutos | Poquísimos, y solo del camino del dinero |

## El hueco real no era e2e

Los dos bugs que motivaron esta estrategia fueron **desacuerdos de
contrato**, no de comportamiento:

- La apertura de caja del PDV mandaba `monto_apertura` cuando el servidor
  ya esperaba `monto_declarado` (ADR-025). Respuesta: 422.
- `GET /ventas` pasó a devolver `{items, total, …}` (ADR-026) y
  `lib/pdv.ts` lo seguía leyendo como array.

Ninguno necesitaba un navegador. Los dos se cazan comparando lo que el
cliente manda contra `docs/architecture/openapi.json`, que **ya se genera y
ya se verifica en CI**. Ese es el test barato que falta y el que hay que
escribir primero:

> Por cada operación que el frontend invoca, afirmar que el cuerpo que arma
> valida contra el `requestBody` del contrato, y que el tipo con el que lee
> la respuesta coincide con el `responseBody`.

Corre en milisegundos, no necesita servidores, no es flaky, y cubre **todas**
las pantallas de una vez en lugar de una por prueba.

## Qué sí justifica un e2e

Tres cosas, y ninguna es una regla de negocio:

1. **Que la sesión funcione**: login → cookie httpOnly → una pantalla
   protegida. Si esto se rompe, no importa qué más ande.
2. **Un solo flujo del dinero completo**: abrir caja → vender → cobrar →
   cerrar. No para verificar el descuadre —eso es dominio— sino para
   verificar que las cuatro pantallas encadenan.
3. **Los candados que solo existen en pantalla**: el diálogo bloqueante de
   apertura (sin caja no se vende), y que un rechazo del servidor deje el
   formulario abierto con lo tecleado en vez de perderlo.

Todo lo demás que se sienta como "hay que probar la pantalla" es, casi
siempre, un test de contrato o de dominio mal ubicado.

## Reglas para escribir un e2e

Aprendidas a los golpes; cada una costó tiempo:

- **Los datos los siembra un seeder versionado** (`src/seeders/e2e.py`), no
  el test. Un test que crea sus datos por la UI prueba tres flujos para
  verificar uno.
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

## Estado actual (2026-08-05)

- Dominio y API: **887 casos**, en verde, en CI.
- Unidad de frontend: 14 casos (`npm test`). **No corren en CI todavía** —
  el job de frontend solo hace `lint` y `build`.
- Contrato cliente↔servidor: **no existe**. Es la prioridad.
- e2e: andamiaje armado y **en rojo**, ver ROADMAP → Frontend.

## Nota de velocidad

La base de desarrollo vive en **Supabase, no en la máquina**: cada consulta
cuesta ~130 ms de ida y vuelta, y toda prueba que pase por HTTP los paga.
Las pruebas automatizadas usan SQLite en memoria o un archivo desechable
justamente por eso — y es también la razón por la que las pantallas se
sienten lentas en desarrollo (ver ROADMAP → Deuda técnica → Transversal).
