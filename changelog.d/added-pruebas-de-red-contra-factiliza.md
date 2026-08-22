- **Las consultas RUC/DNI se prueban también contra Factiliza de verdad**
  (2026-08-22, `tests/test_factiliza_red.py`). Los dobles de `httpx` prueban
  que el cliente manda el token correcto; no prueban que **ese** token sirva.
  La corrida real confirmó las dos mitades: la consulta funciona con
  `FACTILIZA_CONSULTA_DOCUMENTO_TOKEN`, y el token de emisión **no** consulta
  documentos — o sea que tenerlos separados no era una precaución teórica.
- **El suite normal sigue sin salir a internet.** El archivo está marcado
  `red` y `addopts` lleva `-m "not red"`, así que `pytest` a secas —lo que
  corre el CI— no lo toca. Se dispara a mano con `pytest -m red` desde la raíz
  del repo. Sin token, queda `skipped`, no rojo. La alternativa —hacer que el
  suite de siempre pegue a la API— habría atado el CI a que RENIEC y SUNAT
  estén arriba y quemado cuota paga en cada push.
- **Solo consultas, nunca emisión.** Un `POST /invoice/send` real genera un
  comprobante ante SUNAT: eso no lo dispara una prueba.
- Costo aceptado: **no se prueba por red el camino "documento no encontrado"**.
  Dar con un DNI que de verdad no exista obliga a consultar documentos de
  desconocidos hasta que alguno falle — el primer intento devolvió a una
  persona real con nombre y domicilio. Ese caso se queda con dobles, que es
  donde siempre estuvo bien cubierto.
