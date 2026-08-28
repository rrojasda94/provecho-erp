- **El borrador del PDV vive en el servidor** (2026-08-28, ADR-074). El ticket
  a medio armar existía **solo** en `useState`: recargar la página, quedarse
  sin batería o cambiar de turno borraba todas las pestañas de pedido y el
  mesero volvía a teclear la mesa entera. Ahora se guarda contra el **punto de
  venta** —no contra el usuario, para que el relevo siga el pedido que dejó el
  anterior— con autoguardado a los 800 ms de la última tecla. El contenido va
  en JSONB a propósito: un borrador no es un hecho de negocio hasta que se
  envía, y modelarlo en columnas obligaría a una migración cada vez que el
  ticket gane un campo.
- **El proxy del navegador ganó su handler de `PUT`** (2026-08-28). No lo
  tenía. Next responde 405 al verbo que el archivo no exporta, sin decir en
  ningún lado que el que falta es el del proxy y no el del endpoint: el
  guardado del borrador fallaba contra un endpoint que existía y funcionaba.
  Un test del contrato ahora exige un handler por cada verbo que la API usa.
