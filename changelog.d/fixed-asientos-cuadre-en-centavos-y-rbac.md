- **Un asiento que cuadraba se rechazaba por un centavo que no existe**
  (2026-09-04, auditoría del 2026-08-30 §16). El debe contra el haber se
  comparaba con `===` sobre sumas de flotantes, en la pantalla **y** en la
  Server Action: 0.10 + 0.20 contra 0.30 —tres líneas normales— dejaba
  «Registrar» apagado mostrando «Diferencia: 0.00», y si igual llegaba al
  servidor volvía con «el asiento no cuadra». La plata se cuenta ahora en
  centavos (`lib/cuadre.ts`, con pruebas en `npm test`), que es la unidad
  indivisible y donde la igualdad es exacta. Techo declarado: el paso a
  centavos redondea el flotante en vez de parsear el texto decimal, así que
  un importe de tres decimales a mitad de centavo depende de cómo cayó el
  binario — hoy no llega, los campos son `step="0.01"`.
- **«+ Asiento manual» y «Anular» se ofrecían a cualquiera que pudiera leer
  el libro** (2026-09-04, auditoría §3). Los dos exigen
  `accounting.asiento_manual` en la API —anular no borra, escribe el asiento
  inverso (RN-CTB-002)—, y ahora el permiso decide si se dibujan.
- **Errarle a un dato del asiento borraba las líneas ya cargadas**
  (2026-09-04, auditoría §4). El diálogo pasa a `DialogoFormulario`; las
  líneas, que son estado propio de la pantalla, se limpian al abrir y no al
  enviar, así que un rechazo del servidor deja ver lo que se había cargado.
  Verificado en el navegador contra el rechazo real por periodo cerrado.
- **`DialogoFormulario` acepta el ancho del panel** (2026-09-04). Nació con
  `max-w-md` fijo porque las siete pantallas que lo estrenaron eran
  formularios de una columna; un asiento contable lleva una tabla de líneas
  adentro y a ese ancho cada fila se parte en tres renglones.
- **`EstadoAsiento` es `EstadoFormulario`** (2026-09-04). El alias se queda
  —catorce firmas del módulo lo nombran— pero el tipo dejó de ser el par
  `{error, ok}`, que escondía los `campos` rechazados que `estadoDeError` ya
  venía devolviendo y que el diálogo usa para marcar y enfocar el input
  equivocado.
