- **El major de `@types/node` queda en `ignore`** (2026-08-08). Los tipos
  describen el runtime que el código va a encontrar, así que subirlos por
  delante del runtime es peor que quedarse atrás: los de Node 26 aprueban
  APIs que Node 24 —el que corren los jobs `frontend` y `e2e`— no tiene, y
  `tsc` daría verde sobre código que muere en ejecución. Se cerró dos veces
  por el mismo motivo (PR #29 y #55) y volvía cada semana; ahora el motivo
  está escrito donde se toma la decisión. Se quita al subir el CI a Node 26,
  en el mismo cambio: el número del `ignore` y el `node-version:` de `ci.yml`
  son el mismo número.
