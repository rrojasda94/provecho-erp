- **Las mitades de una MitadXMitad nunca llegaban a ninguna pantalla del
  KDS.** `_valores_por_item` (`src/modules/sales/application/kds.py`) las
  resolvía a `"Mitad 1: Americana"` y `_item_a_dict` las emitía, pero
  `ItemColaOut` (`src/modules/sales/api/kds_schemas.py`) no declaraba el
  campo, así que pydantic las descartaba al serializar la cola; y encima la
  rama de **preparación** de `_items_de_pantalla` ni siquiera se las pasaba,
  con lo cual el bug tenía dos capas. Salían en la comanda impresa y en
  ningún otro lado: un pizzero que trabajara solo con la pantalla veía
  "1 Pizza MitadXMitad" sin saber de qué mitades era, que es lo único que
  hay que saber de ese plato (ADR-056). `ItemColaOut` gana
  `valores: list[str]`, el tipo `ItemCola` de `frontend/lib/kds.ts` lo
  espeja y `frontend/app/kds/nombre-linea.tsx` lo dibuja delante de extras y
  restas —mismo orden que el papel, porque los valores dicen QUÉ es el plato
  y lo demás solo lo modifica—.
- **Un campo que el KDS calcula y el schema no declara ahora rompe el CI.**
  Es la tercera vez que pasa lo mismo: `tipo`/`consumo_motivo` (ADR-044),
  después `direccion_entrega` y ahora `valores`. FastAPI filtra el campo al
  serializar sin error, sin warning y sin nada en la pantalla, así que el
  fallo solo se descubre en el local. `test_el_response_model_no_se_come_ningun_campo_de_la_cola`
  (`tests/test_kds.py`) compara las claves que `cola_pantalla`,
  `_item_a_dict`, `avance_venta` y `comanda` construyen contra los campos
  que sus schemas declaran, así que el próximo campo huérfano falla en el
  commit que lo agrega, sea cual sea. El contrato en
  `docs/architecture/openapi.json` quedó regenerado.
