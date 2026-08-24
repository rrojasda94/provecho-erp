# ADR-058 — El lienzo dibuja atributos, y carga el árbol de una vez

- Estado: aceptado
- Fecha: 2026-08-23
- Contexto: `sales` (catálogo), frontend
- Relacionado: ADR-035 (el lienzo de nodos), ADR-042 (la variante hereda),
  ADR-055 (atributos y variantes), ADR-057 (la matriz), RN-COM-036/038

## Contexto

ADR-055 puso los atributos en el modelo y ADR-056 los hizo mover stock. El
lienzo —que es *el* lugar de trabajo del catálogo— seguía dibujando el mundo
anterior: tamaños, grupos y extras. Un atributo declarado no aparecía en
ninguna pantalla, así que el modelo nuevo no se podía ni mirar.

Y arrastraba un problema propio, anotado en su propia deuda: **una petición
HTTP por variante**. `page.tsx` pedía la ficha del padre y después una por
cada tamaño, más una receta por nodo al entrar al plato. Con tres tamaños y
ocho sabores son veintisiete idas a la red para dibujar un árbol.

## Decisión

### 1. `GET /sales/productos/{id}/arbol` — una llamada, todo el árbol

Producto, variantes **con sus grupos y extras**, atributos con sus valores,
exclusiones y combinaciones materializadas.

Cada tamaño sigue trayendo *sus* grupos —"Peperoni" en Personal y en Familiar
son dos opciones distintas con dos recetas distintas, no la misma vista dos
veces—, solo que ahora vienen juntas. Adentro del servidor sigue siendo N
consultas locales; la diferencia con N peticiones HTTP a través del proxy es
de dos órdenes de magnitud. Queda anotado el techo: con veinte variantes,
`grupos_de` y `extras_de` se baten en dos consultas.

**El árbol hereda de `ProductoDetalleOut`**, así que trae también lo viejo.
Con el interruptor `catalogo.modelo_odoo` apagado el lienzo dibuja exactamente
lo de antes, y una sola forma de traer los datos evita que las dos pantallas
se separen.

### 2. El atributo se dibuja como el grupo, y el valor como la opción

No es lo mismo —un grupo agrupa extras, que son productos con receta y precio;
un atributo es una dimensión del plato— y comparten forma porque **el gesto
es el mismo**: elegir uno de varios. El lienzo no gana nada inventando una
segunda manera de mostrar lo que ya se sabe mirar.

Las columnas de atributo van **antes** que las de grupo: RN-PRD-004 leído de
izquierda a derecha sigue siendo la espina de la pantalla, y el atributo es
más cerca del tamaño que del extra.

### 3. Lo excluido se apaga, no se oculta

Elegir "Hawaiana" en la primera mitad apaga "Hawaiana" en la segunda
(RN-COM-038). Apagado y no oculto: media hawaiana **desaparecida** de la
segunda mitad se lee como un error de carga; media hawaiana **apagada** dice
"ya la elegiste".

Y elegir un valor **suelta** los que quedan excluidos por él, en vez de
dejarlos marcados: mostrar un plato que la venta va a rechazar es el mismo
bug de ADR-038 con otra forma.

### 4. El producto y los tamaños guardan dónde quedaron

`producto_comercial.lienzo_pos`. ADR-035 §5 (primera enmienda) decidió **no**
persistir posiciones, con este argumento: *"cualquier cambio de estructura
recoloca todo, y eso es consecuencia aceptada"*. Era cierto mientras el árbol
lo dictaba una topología fija de seis columnas.

Con atributos deja de serlo: el árbol ya no se rearma solo, y perder la
posición en cada recarga es trabajo tirado — es lo que la gente reacomoda
para comparar dos tamaños de un vistazo.

**Solo el producto y los tamaños**, que son filas de `producto_comercial`. Un
nodo de grupo, de valor o de resta no tiene columna que lo reciba, y su lugar
lo sigue dictando la topología. Persistir lo que sí se puede es mejor que no
persistir nada.

Se guarda al **soltar** (`onNodeDragStop`), no en cada cuadro del arrastre:
mover un nodo cincuenta pixeles serían cincuenta `PATCH`. Y **no pasa por el
manejador de errores** de la pantalla: recolocar un nodo no puede bloquear el
lienzo ni pintar un error si falla. Es cosmético, y el próximo arrastre lo
reintenta solo.

### 5. Los atributos se editan por su propia API, no por la del producto

`POST /sales/atributos`, `POST /sales/atributos/{id}/valores`,
`POST /sales/productos/{id}/atributos`, `PATCH|DELETE
/sales/atributos/valores/{ptav_id}`, `POST|DELETE /sales/atributos/exclusiones`.

Un atributo se declara una vez y lo usan cuarenta productos: colgarlo del
endpoint del producto obligaría a inventar "crear el atributo mientras
edito la pizza", que es cómo aparecen tres "Tamaño" distintos.

**Retirar un valor lo desactiva, no lo borra**: hay ventas que lo nombran y
líneas de receta que lo usan como condición.

## Alternativas descartadas

- **Una pantalla nueva para atributos, aparte del lienzo.** Es lo que ADR-023
  §4 ya corrigió para las recetas: lo mismo en dos pantallas hace pensar que
  son dos cosas distintas. El lienzo es el lugar de trabajo del catálogo.
- **Un tipo de nodo propio para el atributo, con otra forma.** Ver §2.
- **Ocultar los valores excluidos.** Ver §3.
- **Persistir la posición de todos los nodos**, agregando una tabla
  `lienzo_nodo`. Una tabla, una migración y un contrato para algo cosmético,
  cuando los nodos que la gente mueve son los que ya tienen fila.
- **Guardar la posición en cada movimiento.** Cincuenta `PATCH` por arrastre.
- **Materializar las variantes desde el lienzo.** El generador de
  combinaciones (`modo_variante = siempre`) todavía no existe; el lienzo
  muestra `combinaciones` para cuando exista. Anotado en Deuda técnica.

## Consecuencias

- `page.tsx` del lienzo pasa de 2 + N peticiones a 5 fijas.
- `frontend/lib/lienzo.ts` gana `columnaDeAtributo`, `valoresExcluidos` y
  `modoLegible`; `Camino` gana `valores`. Las funciones nuevas son puras y
  tienen prueba, igual que el resto del archivo.
- `TIPOS_NODO` gana `atributo` y `valor`, reusando `NodoGrupo` y
  `NodoTarjeta`.
- `ProductoOut` gana `lienzo_pos`, y `ProductoUpdate` lo acepta.
- El árbol devuelve `variantes_detalle`: es lo que antes eran N peticiones.
- El nodo de un **valor** abre las líneas de receta condicionadas a él, y las
  que se agreguen desde ahí nacen con esa condición puesta (enmienda de
  ADR-056, 2026-08-24). Un sabor no tiene receta propia: sus insumos son
  líneas de la receta del tamaño, así que el nodo apunta a esa.
- Queda pendiente: crear un atributo **desde** el lienzo (hoy la API existe y
  la pantalla todavía no tiene el popover), materializar combinaciones, y
  multi-selección para "aplicar a todos los tamaños". Ver Deuda técnica.
