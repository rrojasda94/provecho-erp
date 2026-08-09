- **El lienzo de nodos deja de ser un visor y pasa a ser el lugar donde se
  arma la carta** (2026-08-09, ADR-035 segunda enmienda). Antes se podía
  recorrer y simular; ahora se edita.
  - **La receta se edita dentro del nodo.** Tocar un tamaño, un sabor o un
    extra abre su receta en el inspector: cambiar cantidades, quitar un
    insumo, agregar otro. La cantidad acepta aritmética ("1000/3") y **la
    evalúa el servidor**, no el navegador (RN-COM-024). Esto revierte la
    regla de editar recetas solo en Catálogo → Recetas: lo que ADR-023 §4
    había corregido era la *duplicación* del editor en dos pantallas que no
    se sabían relacionadas, y el lienzo no es una segunda pantalla — es el
    lugar de trabajo. Catálogo → Recetas sigue siendo el dueño de crear,
    duplicar, escalar y renombrar, con enlace desde cada nodo.
  - **Se conectan y desconectan nodos.** El grupo pasa a ser un nodo porque
    es el destino de la conexión, y los extras que el producto todavía no
    ofrece aparecen apagados en su propia columna para poder cablearlos:
    arrastrar de un grupo a uno de ellos lo cuelga **dentro** de ese grupo;
    del tamaño, lo deja suelto; cortar la arista lo desvincula sin borrar el
    extra. Cualquier otro par se rechaza con un mensaje que dice qué sí se
    puede — la topología tamaño → sabor → plato la dicta RN-PRD-004 y no se
    negocia con el mouse.
  - Una columna que se envuelve en subcolumnas ahora **reserva su ancho**:
    con 18 extras disponibles, la columna de restas se le montaba encima.
- **Carta de pizzas de demo armada con el modelo de nodos**
  (`python -m src.seeders.pizzas_demo`). El catálogo de demo anterior
  modelaba cada combinación como un producto plano —"Pizza pepperoni
  familiar", "Pizza hawaiana mediana"—, que es justo lo que el lienzo vino a
  reemplazar: seis sabores por tres tamaños serían dieciocho productos,
  dieciocho precios y dieciocho recetas a mano. Ahora es **una** Pizza con
  tres tamaños, un grupo Sabor obligatorio de seis opciones con receta
  propia por tamaño, cuatro extras y empaque por modalidad. `--limpiar`
  **desactiva** lo que no es pizza en vez de borrarlo: un producto vendido se
  descontinúa (misma regla que `eliminar_producto`) y el catálogo anterior no
  lo genera ningún seeder del repo, así que borrarlo sería destruir algo que
  nadie puede recrear.
- **El insumo de demo del e2e tiene costo** y **el servidor de e2e sube el
  rate limit de login**: la suite entra once veces desde la misma IP y el
  límite real son diez por minuto, así que las últimas pruebas fallaban con
  "no aparece el inicio", que no menciona el rate limit por ningún lado.
