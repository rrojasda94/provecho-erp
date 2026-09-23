# ADR-106 — El PDV es un módulo propio del home, no un enlace del sidebar de Ventas

Fecha: 2026-09-23
Estado: aceptada (reemplaza la decisión de navegación de ADR-013 sobre el PDV)

## Contexto

Hasta acá el PDV se abría desde **Ventas → Abrir el PDV**: la ficha del home
entraba al back-office (jornada de la sucursal) y el PDV era el último ítem
de su sidebar. La razón escrita en `lib/modulos.ts` era que un tile directo
al PDV "dejaba sin puerta a lo administrativo".

En uso real pasa lo contrario: quien abre el PDV es el cajero, varias veces
por turno, y no administra la jornada; quien administra casi nunca vende.
Poner la pantalla más usada detrás de un módulo que no es suyo suma un clic
y un desvío mental a cada apertura. El KDS ya tenía su propia ficha y nadie
lo extrañó dentro de otro módulo.

## Decisión

- El PDV es un módulo del home (`clave: "pdv"`, área **Operación**, ícono
  `MonitorSmartphone`) que abre `/pdv` directo. Sigue siendo pantalla
  completa táctil fuera del shell (ADR-013).
- Se ve con el permiso **exacto** `sales.crear`, no con el prefijo `sales.`:
  quien solo lee ventas no vende, y con el prefijo vería una ficha que
  termina en 403. `/pdv` aplica el mismo gate y muestra un bloqueo que dice
  qué permiso pedir.
- Ventas queda como back-office: jornada, clientes, mesas y promociones. Su
  sidebar ya no tiene "Abrir el PDV".
- **El backend no cambia.** La venta sigue siendo dominio de `sales`; esto es
  navegación, no un módulo nuevo de backend. La URL `/pdv` tampoco cambia.

## Consecuencias

- Una ficha más en el home para quien tiene `sales.crear`.
- Lo administrativo sigue teniendo puerta: la ficha de Ventas.
- `rastro.ts` ahora reconoce `/pdv` como módulo ("Inicio › Punto de venta").
