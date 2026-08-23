- **La imagen lleva `scripts/odoo`.** El README del cargador manda correrlo
  dentro del contenedor —`docker compose exec api python -m
  scripts.odoo.cargar_catalogo`— y el `Dockerfile` copiaba solo `src`,
  `alembic` y los archivos de proyecto. El comando documentado fallaba con
  `No module named 'scripts'`, y no hay forma de enterarse sin desplegar:
  pasó al cargar el catálogo en staging.

  Entra `scripts/odoo` y nada más de `scripts/`: `cortar_version.py` y
  `empaquetar_demo.py` son herramientas de desarrollo, y `desplegar.sh` y
  `backup-staging.sh` corren en el host.

  Con guardarraíl: `test_la_imagen_lleva_lo_que_se_corre_dentro_del_contenedor`
  falla si el README vuelve a mandar algo que la imagen no tiene.
