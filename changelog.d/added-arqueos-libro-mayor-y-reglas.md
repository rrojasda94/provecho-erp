- **El libro contable se puede recorrer** (2026-09-05, Ola 3 de la auditoría
  del 2026-08-30). Tres endpoints entregados y probados que ninguna pantalla
  llamaba:
  - **Libro mayor** (`/contabilidad/libro-mayor`): todo lo que movió una
    cuenta, en orden y con el saldo corriendo. Estados financieros usa el
    balance de comprobación, que dice **cuánto** tiene cada cuenta y no de
    dónde salió: con un saldo raro no había forma de abrirlo. Cuenta y rango
    viajan en la URL, así que el mayor de una cuenta en un periodo es una
    dirección que se comparte.
  - **Detalle de asiento** (`/contabilidad/asientos/[id]`): contra qué
    cuentas se escribió. El listado mostraba fecha, glosa, origen y estado, y
    nunca las líneas — un asiento automático que salía raro no se podía
    revisar sin entrar a la base. Se navega en los dos sentidos: del mayor al
    asiento y de cada línea del asiento al mayor de su cuenta.
  - **Reglas de asiento** (`/contabilidad/reglas-asiento`): con qué cuentas
    se asienta cada hecho. Los eventos se eligen de una lista y no se
    teclean: adivinar el nombre exacto es la forma más fácil de escribir una
    regla que no se aplica nunca, y la pantalla marca las que apuntan a
    eventos que el ERP ya no publica. Se ve además cuáles usan la plantilla
    de fábrica del PCGE, que es lo esperable.
- **El arqueo de caja vuelve a poder mirarse** (2026-09-05). `POST /arqueos`
  existía desde el ciclo de caja y **no había `GET`**: el conteo quedaba en la
  base y en ningún lado más, que es lo mismo que no haberlo hecho — el arqueo
  sirve por su historia. Ahora se registra y se lista desde Contabilidad →
  Caja, sobre las cajas abiertas, que son las únicas que tienen cajón que
  contar. El monto esperado sigue saliendo del servidor: si lo mandara la
  pantalla, el arqueo dejaría de probar nada (PROC-CTB-005).
