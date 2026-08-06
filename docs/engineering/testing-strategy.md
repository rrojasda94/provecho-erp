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
ya se verifica en CI**.

✅ **Escrito el 2026-08-06** (`frontend/lib/contrato.test.ts`, 58 casos en
~250 ms). Son **dos capas**, y la primera importa más que la segunda:

**1. El tipo, que es el que trabaja todo el día.** Los cinco cuerpos de
request del PDV viajaban como `Record<string, unknown>` — sin contrato del
lado del cliente, que es por donde entró el bug de ADR-025. Tipados desde
`openapi.json`, `tsc` los verifica **en cada punto de llamada** y ya corre
en CI. Tiparlos destapó cinco desacuerdos el primer día, entre ellos que
`PosVerificado` (lo que se lee, con `serie`) no es `PosVerificadoIn` (lo que
se manda), y dos enums que viajaban como `string` suelto.

**2. El test, que verifica que esos tipos y el contrato digan lo mismo.**
Por cada operación de `lib/pdv.ts`, con `fetch` intervenido: que la ruta y
el método existan en el contrato, que el cuerpo valide contra su
`requestBody`, y —alimentando al cliente con una respuesta **generada desde
el contrato**— que la sepa leer. Esto último es lo que caza ADR-026: el
cliente recibe `{items, total, …}` de verdad y tiene que devolver un array.

El validador cubre a propósito solo lo que se rompe en silencio: requerido
que no viaja, campo que el contrato no conoce, tipo equivocado. `pattern`,
`minimum` y enums los rechaza el servidor con un 422 que **se ve**;
replicarlos acá sería mantener dos validadores desincronizándose.

Verificado por mutación, que es lo único que prueba que un test verde pueda
ponerse rojo: reintroducidos los dos bugs históricos (más un endpoint
renombrado), los tres fallan con el nombre de la operación y el del campo.

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
- **La prueba pasa por los candados, no los rodea.** Si la pantalla exige un
  paso antes de cobrar, el test lo da: saltárselo no prueba el flujo del
  cajero, prueba uno que no existe.
- **Presupuesto de tiempo generoso en modo desarrollo.** `next dev` compila
  cada ruta la primera vez que se la pide. Un timeout corto no falla donde
  está el problema: falla donde se acabó el reloj, y como cada corrida deja
  la caché más tibia, el punto de falla se mueve solo. Eso se lee como
  flakiness y no lo es.

## Estado actual (2026-08-06)

- Dominio y API: **895 casos**, en verde, en CI.
- Unidad de frontend + contrato: **72 casos** (`npm test`), en CI desde
  2026-08-06 — el job de frontend hacía solo `lint` y `build`. De esos, 58
  son de contrato.
- e2e: **7 casos en verde y en CI** (job `e2e`), sobre PDV, sesión y el gate
  de módulo. Los tres puntos de "qué sí justifica un e2e" quedan cubiertos.
  Ver ROADMAP → Frontend.

Los cuatro niveles de la tabla existen. **Lo que falta ya no es un nivel
sino cobertura**: el contrato cubre las 19 operaciones del PDV, y las de
Compras, Inventario, RRHH y el resto del back-office siguen sin él —
`lib/cliente-api.ts` y los Server Components llaman a la API por su cuenta.
Extenderlo es repetir el patrón, no inventarlo.

## Nota de velocidad

La base de desarrollo vive en **Supabase, no en la máquina**: cada consulta
cuesta ~130 ms de ida y vuelta, y toda prueba que pase por HTTP los paga.
Las pruebas automatizadas usan SQLite en memoria o un archivo desechable
justamente por eso — y es también la razón por la que las pantallas se
sienten lentas en desarrollo (ver ROADMAP → Deuda técnica → Transversal).
