# Migrar el catálogo de Odoo a Provecho

Dos pasos: **convertir** el export de Odoo a las planillas de Provecho, y
**cargar**. El primero no toca la base; el segundo tiene modo simulación.

```bash
# 1. Convertir. Escribe seis libros numerados + INFORME.md
python -m scripts.odoo.convertir_catalogo \
    --origen "<carpeta con los 4 .xlsx de Odoo>" \
    --salida salida-catalogo

# 2. Leer INFORME.md. Vetar correcciones editando las planillas si hace falta.

# 3. Simular la carga: resuelve todo y deshace al final
python -m scripts.odoo.cargar_catalogo --origen salida-catalogo --simular

# 4. Cargar de verdad, cuando la simulación sale sin problemas
python -m scripts.odoo.cargar_catalogo --origen salida-catalogo
```

## Qué espera de Odoo

Cuatro exports de `product.template`, `product.attribute` y `mrp.bom`, con los
nombres que Odoo les pone por defecto:

| Archivo | Modelo |
|---|---|
| `Producto plantilla.xlsx` | `product.template` |
| `Atributo de producto para pizzas.xlsx` | `product.attribute` |
| `Lista de materiales Recetas.xlsx` | `mrp.bom` |
| `Lista de materiales MITADXMITAD.xlsx` | `mrp.bom` con `bom_product_template_attribute_value_ids` |

Se leen en el formato o2m de Odoo —fila padre y filas hijas con solo las
columnas hijas llenas— tal cual sale de "Exportar".

## El orden importa

Cada libro referencia **por nombre** lo que creó el anterior:

```
1 fundaciones  →  2 artículos  →  3 recetas  →  4 atributos  →  5 productos  →  6 mitad×mitad
   UdM, categorías          insumos      cabeceras y      atributos y      productos,      solo las líneas
                                          líneas simples   sus valores      variantes y     condicionadas
                                                                            precios
```

El 6 va último porque sus líneas se condicionan a valores de atributo que solo
existen cuando el producto los declara (libro 5). Y las **cabeceras** de esas
dos recetas van en el libro 3, no en el 6: el producto necesita su
`receta_id` antes de poder declarar atributos, así que la receta tiene que
existir vacía primero. Sin esa separación la dependencia es circular.

## Por qué un script y no la pantalla de importar

Los importadores de artículos y recetas existen (ADR-046, ADR-052) y esta
carga los respeta: usa los mismos casos de uso, así que las reglas son las
mismas. Lo que no tiene sentido es revisar a mano, en seis diálogos, las 1300
filas de una carga inicial que se hace una vez. Para el trabajo de todos los
días —corregir treinta gramajes— la pantalla sigue siendo el camino.

## Qué corrige, y qué no

**No inventa datos de negocio.** Un gramaje que en Odoo viene en cero no se
completa: sale del libro principal y queda en `7-pendiente-cantidades.xlsx`.

Sí corrige incoherencias donde el archivo se contradice y hay una sola lectura
defendible —unidades que no son las que las recetas consumen, nombres
duplicados, categorías cuya hoja choca, vendibles sin receta—. Cada una queda
escrita en `INFORME.md` con el valor viejo y el nuevo, para poder vetarla
editando la planilla antes de subir.
