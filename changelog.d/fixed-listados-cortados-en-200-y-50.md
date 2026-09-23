- **Artículos, y otros ~45 listados, se cortaban en silencio** (2026-09-23,
  enmienda a ADR-026). La lista de artículos pedía una página de 200 y
  buscaba en el navegador: el 201 no aparecía ni buscándolo. Ahora pagina y
  busca en el servidor (URL `?q&page&page_size`), y cada nombre lleva a la
  ficha del artículo. El libro contable hace lo mismo y ganó búsqueda por
  glosa en la API (`GET /accounting/asientos?q=`). Donde ni se pasaba
  `page_size` el corte era en la fila **50**: proveedores, trabajadores,
  usuarios, traslados, conteos, OCs, planes de producción, informes… Esos
  listados ahora traen todas las páginas (`apiFetchCompleto`), igual que las
  ventas del día en el PDV y el catálogo del importador de recetas.
