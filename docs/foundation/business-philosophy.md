# Filosofía del negocio

Principios invariantes del ERP. No describen tecnología: describen cómo el
sistema representa la realidad del negocio. Toda decisión de arquitectura,
dominio y datos debe ser coherente con estos principios. Si una propuesta los
contradice, la propuesta está mal.

## Principios

1. **La realidad operativa primero, la contable después.** El sistema modela lo
   que pasa físicamente (compras, movimientos, ventas); la contabilidad
   *refleja* esos eventos, no los reemplaza ni los precede.

2. **El inventario pertenece a un almacén, nunca a una marca.** El stock vive en
   almacenes. Las marcas no tienen stock; venden.

3. **Las marcas venden productos comerciales.** Un producto comercial pertenece
   a una marca.

4. **Los productos comerciales consumen recetas.** Vender no descuenta stock
   directo: descuenta a través de la receta.

5. **Las recetas consumen artículos (SKUs).** Insumos y subrecetas son lo
   inventariable; la receta los enlaza.

6. **Ningún movimiento elimina información histórica.** Todo es aditivo:
   correcciones por contramovimiento o anulación, nunca por borrado.

7. **Todo movimiento genera auditoría.** Quién, qué, cuándo, dónde, antes y
   después. Sin excepción.

8. **Multiempresa desde el núcleo.** El aislamiento por tenant no es una capa
   añadida: está en el centro del modelo. Toda consulta nace con contexto.

9. **La contabilidad refleja los eventos operativos, no los sustituye.** Los
   asientos se derivan de eventos del dominio; no se capturan a mano salvo
   excepción controlada.

10. **Humanos y agentes de IA juegan con las mismas reglas.** La IA no tiene
    atajos en el dominio; solo permisos distintos.

11. **El sistema es modular por diseño.** Toda capacidad se puede agregar o
    quitar sin romper el resto. Ningún módulo conoce el interior de otro.

> Estos principios son la "constitución" del proyecto. Cambiarlos es una
> decisión mayor y requiere un ADR.
