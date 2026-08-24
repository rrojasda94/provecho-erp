# ADR-060 — El cupón de la landing pública vive en `sales`, y el descuento reusa el de la orden

- **Estado:** aceptada
- **Fecha:** 2026-08-24
- **Contexto:** `sales` (cliente, venta, cupón), `marketing` (campaña, lead)
- **Relacionado:** ADR-004 (aislamiento de tenant), ADR-011 (ARCO:
  anonimización, no borrado), ADR-018 (descuento de orden), ADR-021
  (atribución lead→venta), ADR-029 (la encuesta pública), ADR-053 (la
  dirección se elige en el mapa)

## Contexto

Grupo Majambo quiere el padrón de clientes de Charlie's Pizzas. La mecánica:
un QR en la mesa lleva a una landing —**«Queremos RE-conocerte»**— donde el
cliente deja DNI, cumpleaños, dirección y teléfono, y a cambio recibe **10 %
de descuento** para su siguiente compra. Un cupón por persona, de un solo uso,
válido un mes; la campaña termina a fin de año y la empresa puede cortarla
antes.

Es la primera pantalla del sistema dirigida a un cliente del restaurante y no
a un trabajador, y trae tres decisiones que no tenían respuesta previa.

## Decisión

### 1. El cupón es de `sales`, no de `marketing`

Parece de Marketing —es una campaña con un QR— pero las dos operaciones que
hace son **escrituras dentro de `sales`**: crear o encontrar un `cliente`, y
descontar una `venta`.

`tests/test_arquitectura.py` sólo deja que un módulo entre a otro por
`api.deps` o `application.queries_publicas`, y su docstring es explícito
—*«la lista puede encogerse, nunca crecer sin una decisión explícita»*—. Poner
el cupón en `marketing` obligaba a una de tres cosas, todas peores:

- **Ampliar la lista de excepciones** para dejar a `marketing` escribir en
  `sales`. Es exactamente la deuda que esa lista existe para no seguir
  acumulando.
- **Un contrato público de escritura.** `queries_publicas` es de lectura por
  definición; inventar el gemelo de escritura es abrir la puerta a que
  cualquier módulo escriba en cualquier otro, con más ceremonia y la misma
  consecuencia.
- **Hacerlo por eventos.** Los eventos se despachan post-commit y son
  best-effort (ADR-016). Un descuento que a veces no se aplica no es una
  opción.

`cliente` ya vive en `sales` y ya cuelga del grupo (RN-PTS-001), que es lo que
el cupón necesita. `cuenta_puntos` y `puntos_movimiento` están especificadas
en la §6 del modelo de datos —Ventas—, así que los beneficios al cliente ya
tenían ese domicilio.

**Marketing no se queda afuera:** `sales` publica
`sales.cliente_registrado_en_promocion` y el listener de `marketing` crea su
`lead` de tipo `registro`, igual que ya hace con `sales.venta_confirmada`
(ADR-021). El emparejamiento es **por nombre** con una campaña `en_curso`,
porque `marketing` no puede leer `promocion_cupon`. Sin campaña abierta no hay
lead, y eso es correcto: el lead es cómo Marketing mide, no parte de lo que se
le prometió al cliente — frenar un registro porque nadie abrió el brief lo
dejaría sin su cupón por un trámite interno.

### 2. El descuento reusa `venta.descuento_*`, con motivo propio `cupon`

La deuda de `sales` dice que el **motor de promociones condicionales** no debe
reusar esos campos (ADR-018 → «frontera explícita»), porque son de un acto
humano autorizado y mezclarlos haría imposible auditar cuál descuento fue
manual y cuál automático.

Un cupón no es ese motor. No se activa solo: lo trae el cliente y lo teclea el
cajero. Y la alternativa —un canal de descuento paralelo, con columnas
propias— obligaba a tocar `total_a_cobrar`, el prorrateo a las líneas que
exige SUNAT en el comprobante y las notas de crédito. Es la parte del sistema
que maneja dinero y ya funciona.

Lo que se hace en cambio:

- `MOTIVOS_DESCUENTO` gana el valor **`cupon`**, distinto de `promocion`. Es lo
  que deja al reporte de descuentos separar el margen que se regaló a criterio
  de alguien del que se había prometido en una campaña — que es exactamente la
  auditabilidad que ADR-018 protege.
- `cupon.venta_id` cierra el vínculo en la otra dirección: de cada descuento
  por cupón se sabe cuál cupón fue, de quién y de qué campaña.
- **El canje no pide PIN de supervisor.** `POST /ventas/{id}/cupon` va con
  `sales.cobrar` y nada más, a diferencia de `POST /ventas/{id}/descuento`
  (RN-COM-017). El cupón *es* la autorización; pedir un supervisor por cada
  uno haría que la caja deje de canjearlos, que es la forma más segura de
  romper la promesa de la campaña.
- Sólo un descuento por orden: `venta.descuento_*` es una fila, no una lista.
  Con un descuento manual puesto, el canje devuelve 409 en vez de pisarlo.

**Lo que queda pendiente:** el día que exista el motor condicional, sigue sin
poder reusar estos campos. Esta decisión no lo habilita — al contrario, deja
`cupon` como el precedente de que un beneficio automático necesita su propio
lugar.

### 3. La superficie pública escribe, no borra, y lee un booleano

`sales/api/publico_routers.py` es la segunda superficie sin JWT del sistema
(la primera es la encuesta, ADR-029). Se rige por lo mismo, con una diferencia
que endurece el resto: **ni siquiera trae un token**. La encuesta al menos
tiene el del enlace; acá el QR está impreso en una mesa y cualquiera lo
escanea.

De ahí las tres reglas:

- **Ningún `DELETE`.** La baja de datos es un derecho ARCO y se atiende por el
  correo de los términos (`hola@majambo.com.pe`, asunto «BORRAR DATOS») con la
  anonimización de `persona` que ya existe (ADR-011) — nunca desde una página
  abierta a internet.
- **La consulta devuelve `{"registrado": bool}` y nada más.** Ni nombre, ni
  teléfono, ni fecha del cupón. Con cualquier cosa más, el endpoint sería un
  buscador del padrón para quien sepa un DNI.
- **El `grupo_id` sale de la promoción activa, jamás del request.** Uno que
  viniera de afuera sería permiso para escribir en otro tenant (ADR-004). Con
  dos promociones activas el caso de uso corta con 409 en vez de elegir una:
  un descuento cargado contra la campaña equivocada no se nota hasta que
  alguien cuadra los números.

- **El teléfono reconoce, pero no reescribe una identidad.** Buscar por
  teléfono existe porque en caja se da de alta con solo eso (RN-PTS-002) y
  sin ese camino media base entraría duplicada. Pero solo se le completa el
  documento a quien **no tiene ninguno**: sin ese candado bastaría saber un
  teléfono ajeno para cambiarle el DNI a su dueño desde una página abierta a
  internet —y quedarse, de paso, con su historial de compras—. Un teléfono
  que ya pertenece a alguien identificado se ignora y el registro sigue como
  cliente nuevo. Dos fichas que comparten teléfono son un problema de calidad
  de datos que alguien limpia; una identidad pisada, no. (Encontrado
  probando el flujo contra la API real, no en los tests.)

Lo único que protege estos endpoints es el rate limit por IP, en tres niveles
según lo que cuesta cada llamada: 10/hora el registro (crea filas), 20/hora la
consulta (lee un booleano) y **5/hora** el que convierte un DNI en un nombre.

## Lo que se acepta

**El código del cupón es el DNI.** Lo pidió el negocio y tiene una ventaja
real: el cliente no tiene nada que recordar ni guardar, y devolvérselo en la
respuesta no filtra nada porque es el número que él mismo acaba de teclear.

El costo es que **quien conozca un DNI ajeno podría intentar su cupón**. Se
acota atándolo al cliente: el canje exige que la venta tenga `cliente_id` y
que sea el mismo del cupón, así que llevárselo implicaría además hacerse pasar
por esa persona en el mostrador. No se elimina — un código aleatorio lo
eliminaría, a cambio de que el cliente tenga que guardarlo.

**El endpoint que devuelve el nombre de RENIEC permite enumerar DNIs.** Es el
precio de que el cliente confirme su nombre en vez de teclearlo. Mitigado con
el límite más duro de los tres (5/hora por IP) y sin devolver nada más que el
nombre. Si alguna vez pesa más el riesgo que la comodidad, se saca el endpoint
y el nombre se escribe a mano: el formulario ya funciona así cuando Factiliza
no contesta (RN-PTS-004).

## Alternativas descartadas

- **Un módulo `promociones` nuevo.** Activarlo son siete registros fuera del
  módulo (`docs/engineering/module-guide.md`) y seguiría sin poder escribir en
  `sales`, que es el problema real.
- **Reusar la `promocion` de `data-model.md` §6.** Esa entidad liga una lista
  de precios, material promocional y guion de atención, y no existe. Construirla
  entera para emitir cupones sería especificar de más algo que el negocio aún no
  usa; `promocion_cupon` hace una sola cosa y lo dice en el nombre.
- **Sembrar la promoción desde la migración.** La resucitaría en cada
  `downgrade`/`upgrade`, incluso después de que alguien la terminó a propósito.
  Va en el seeder, con `_get_or_create`.
