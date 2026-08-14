# ADR-042 — La variante hereda los grupos y extras de su padre

- Estado: aceptado
- Fecha: 2026-08-12

## Contexto

ADR-038 arregló que la carta leyera los grupos de opciones del producto
**padre** cuando cuelgan de la **variante**, que es como los deja el seeder.
El usuario volvió a reportar lo mismo: *"El problema de los productos
comerciales como la pizza sigue mal. No puedo elegir el sabor."*

El arreglo era correcto y estaba incompleto. Un catálogo armado **a mano**
queda al revés que el del seeder, y por una razón concreta: el lienzo cuelga
"+ grupo" del **nodo activo**, y el nodo activo es el padre mientras el
producto no tiene tamaños. El recorrido natural es

1. crear el producto "Pizza",
2. abrirlo en el lienzo y crear el grupo "Sabor" con sus opciones —que a esa
   altura van al padre, porque no hay otra cosa—,
3. recién después agregar Personal / Mediana / Familiar.

Resultado: los sabores en el padre, las variantes vacías, y la carta —que
desde ADR-038 lee los de la variante— sin nada que ofrecer. La versión
anterior fallaba con el catálogo del seeder; esta, con el que arma una
persona. **Dónde quedó colgado el grupo no debería decidir nada**, y mientras
eso importe siempre va a haber una mitad de los casos rota.

## Decisión

**Una variante ofrece lo suyo más lo de su padre.** Tres métodos en
`ProductoComercialRepo` lo dicen una sola vez:

- `grupos_efectivos(producto)` — los del padre y los propios.
- `extras_efectivos(producto)` — ídem, y **el vínculo propio gana** sobre el
  heredado: si la Familiar declara su propio "extra queso", su `maximo` y su
  grupo son más específicos que los del padre. Sin esa regla, el mismo extra
  aparecería dos veces en la carta.
- `admite_extra_efectivo(producto, extra_id)` — la que usa la venta.

Los métodos crudos (`grupos_de`, `extras_de`, `admite_extra`) **siguen siendo
por producto** y los usa la ficha de catálogo, que edita lo que cuelga de
*este* producto y no lo que hereda. Editar lo heredado desde el hijo es cómo
se termina con dos copias del mismo grupo.

**La venta acepta exactamente lo que la carta ofrece.** `_armar_extras` y
`_validar_grupos` pasan a los efectivos. Es el punto entero: rechazar al
confirmar un extra que la pantalla acaba de ofrecer manda al cajero a un error
que no puede corregir, que es el síntoma que se reportó las dos veces.

**El grupo obligatorio del padre obliga en todos sus tamaños.** "Elige un
sabor" no deja de valer porque el cliente pidió la familiar.

**Un solo nivel.** `producto_padre_id` no encadena: una variante no tiene
variantes (RN-COM-022). No hay recursión que escribir ni ciclo que evitar.

## Alternativas descartadas

- **Migrar los grupos del padre a cada variante** (backfill de una vez): mueve
  el problema a la próxima vez que alguien arme un producto en el orden
  natural. La causa no son los datos, es que el lugar importe.
- **Hacer que el lienzo cuelgue siempre de la variante**: no hay variante
  cuando el producto todavía no tiene tamaños, y obligar a crear los tamaños
  primero es un orden que nadie tiene por qué adivinar.
- **Fusionar en la carta y no en la venta**: es exactamente el bug de
  ADR-038 al revés — la pantalla ofrece y el servidor rechaza.
- **Que el hijo pueda "desheredar"** un extra del padre: no hay caso pedido, y
  sería una tercera cosa que mirar para saber qué se ofrece.

## Consecuencias

- Sin migración: es una regla de lectura, no un cambio de esquema. Los dos
  catálogos que hay hoy —el del seeder, con los grupos en la variante, y el
  armado a mano, con los grupos en el padre— funcionan sin tocar sus datos.
- `GET /carta` puede devolver más extras por variante que antes. Es aditivo
  para el PDV, que ya los agrupa por `grupo_id`.
- El costo de la carta sube: `extras_efectivos` hace dos consultas en vez de
  una para cada variante. Ya estaba anotado como N+1 en Deuda técnica y sigue
  ahí; el arreglo es el mismo (dos consultas por marca, agrupadas en memoria).
- `catalogo.detalle_producto` **no cambia**: la ficha edita lo propio. Queda
  anotado que esa pantalla no muestra lo heredado, que es lo que el lienzo sí
  hace.
