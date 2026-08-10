- **Los reportes de la base de desarrollo no se podían usar para nada**
  (2026-08-10). Eran de pruebas sueltas: títulos sin entidad detrás, sin
  actor y sin destino, así que con ADR-036 el botón «ir al registro» llevaba
  a un 404 y la columna «Quién» decía «Sistema» en todas las filas. Nuevo
  `python -m src.seeders.reportes_demo`: borra lo viejo y arma diez
  situaciones con su fila real —un ajuste de −18 pendiente de aprobar, un
  lote vencido hace cuatro días, una caja con S/ 35.50 de faltante, un pago
  de S/ 4800 sobre el umbral— más tres cadenas de escalamiento (abierta,
  elevada a comercial, resuelta). Los hechos se insertan y **el reporte se
  emite por el camino real**: mismo listener, misma resolución de
  destinatarios, misma bandeja.
- **El reparto de la demo respeta el RBAC, no al revés.** Cada cadena la abre
  y la cierra alguien que de verdad puede: la doble puerta de RN-REP-002
  también aplica al escalamiento, y una demo donde el protagonista recibe un
  403 al abrir su propia cadena enseña lo contrario de lo que quiere enseñar.
- **`jefe_cocina` gana `reports.escalamiento_resolver`.** Sin él, una no
  conformidad de producción solo la podía cerrar alguien sin
  `production.leer` — o sea, nadie. RN-PRD-014 ya decía que «el jefe de
  cocina redacta el hallazgo y la acción tomada».
- **`production.no_conformidad_detectada` ahora también avisa al área
  Cocina.** Iba a Gerencia y Almacén: a todos menos a quien RN-PRD-014 pone
  a actuar.
- **La ficha de un reporte de escalamiento ya no ofrece botón de destino.**
  La cadena se ve más abajo en esa misma ficha, y su lectura se gatea contra
  el módulo del reporte de origen, no contra `reports.leer`: era el único
  enlace que podía prometer acceso y terminar en 403.
