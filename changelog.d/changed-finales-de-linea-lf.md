- **Todo el repositorio pasa a LF, y `.gitattributes` lo hace cumplir**
  (2026-08-08). `CLAUDE.md` → Formato exigía LF desde el principio, pero no
  había nada que lo aplicara: convivían **789 archivos en LF con 116 en CRLF
  y 2 mezclados**, según el sistema donde se hubiera editado cada uno.
  - El costo no es estético. Cuando dos ramas tocan el mismo archivo y una lo
    guardó en CRLF, git no ve tres líneas distintas: ve el archivo entero
    distinto, y el merge se vuelve un conflicto de 3.000 líneas que nadie
    puede revisar. Pasó dos veces el mismo 2026-08-08, con `ROADMAP.md` y con
    `docs/security/security.md`, y ninguna de las dos veces el contenido se
    contradecía.
  - `* text=auto eol=lf` normaliza el índice y el checkout en cualquier
    sistema operativo. `text=auto` deja que git detecte qué es texto, y los
    tres binarios del repositorio (dos `.docx` y el `.bpm` de Bizagi) quedan
    además pinneados explícitos: son formatos comprimidos y una sola
    conversión los corrompe sin aviso.
  - El commit toca 118 archivos y **no cambia una sola línea de contenido**:
    `git diff --ignore-cr-at-eol` sobre el cambio devuelve solo el propio
    `.gitattributes`.
