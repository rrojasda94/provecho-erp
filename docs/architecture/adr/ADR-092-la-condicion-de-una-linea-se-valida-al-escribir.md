# ADR-092 — La condición de una línea se valida al escribir

- Estado: aceptado
- Fecha: 2026-09-06
- Contexto: `src/modules/sales/application/queries_publicas.py`,
  `src/modules/inventory/application/recetas.py`
- Relacionado: ADR-056 (líneas de receta condicionadas), ADR-058 (editor de
  la condición), ADR-063 (los atributos vuelven a la tabla), RN-COM-037

## Contexto

`receta_item.aplica_valores` guarda ids de `producto_atributo_valor`
(PTAV), una tabla de `sales`. `inventory` nunca pudo verificar contra su
propio ORM que esos valores pertenecieran al producto que usa la receta —
son módulos distintos y el límite es real (`tests/test_arquitectura.py` lo
hace cumplir).

El único guardarraíl era la lectura conservadora de
`domain/rules.aplica_a_variante`: un valor que no reconoce forma su propio
grupo, y la línea con un grupo huérfano no aplica nunca. Alcanza para no
descontar de más —el lado caro— pero deja pasar una receta mal armada sin
avisar: una condición con un PTAV inventado o de otro producto se guarda
igual, y el síntoma aparece semanas después como un ingrediente que falta
en la comanda de nadie sabe qué línea.

El editor (`components/catalogo/receta-editor.tsx`) ya reduce el caso malo
al mínimo — solo ofrece las casillas de los valores del producto abierto —
pero eso dejaba el caso a un cliente que llame la API a mano o a una carga
masiva. El servidor seguía sin verificar nada.

## Decisión

**`sales.application.queries_publicas` expone `valores_ofrecidos_de_receta`.**
Envuelve `catalogo.valores_ofrecidos` (ya existente, por producto —
ADR-042: propio más lo heredado del padre) sumado por cada producto que usa
la receta, mismo cálculo que ya hacía `atributos_de_receta` puertas adentro
para armar los ejes que ve el editor. No se reusa esa función directamente
porque devuelve nombres para mostrar; acá solo hace falta el conjunto de
ids para comparar.

**`inventory.recetas` valida en la escritura, no en la lectura.**
`agregar_item` y `editar_item` (vía `_cambiar_condicion`) rechazan con 409
si algún valor de `aplica_valores` no está en ese conjunto.
`rules.aplica_a_variante` no cambia: sigue siendo el guardarraíl de lo que
ya está guardado, conservador con lo que no reconoce. Una condición
guardada antes de este ADR nunca se revalida sola — si el servidor
empezara a rechazar en la lectura, una receta que hoy funciona podría
volverse ilegible por un cambio de catálogo que no tiene nada que ver con
ella.

**Receta que ningún producto usa: se acepta cualquier valor.** Sin producto
no hay conjunto contra el cual comparar —`valores_ofrecidos_de_receta`
devuelve vacío—, y el editor ya esconde la columna en ese caso (ADR-063
§4). Exigir algo ahí sería inventar una regla sobre un dato que todavía no
existe.

## Consecuencias

- Import diferido en `queries_publicas.py`
  (`from sales.application import catalogo` dentro de la función, no al
  tope del archivo): a nivel de módulo el ciclo se cierra —`catalogo`
  importa `inventory.queries_publicas`, que importa `inventory.recetas`,
  que importa `sales.queries_publicas`—. Mismo patrón que ya usan
  `comprobantes.py` y `tarifa_delivery.py` para el mismo problema.
- Las 26 pruebas de `test_receta_condicionada.py` y las de
  `test_recetas_variantes.py` siguen en verde sin tocarlas: ninguna cuelga
  su receta de un producto, así que la validación nueva es un no-op para
  ellas. El caso de rechazo se prueba en `test_atributos_catalogo.py`, con
  un producto real de por medio.
