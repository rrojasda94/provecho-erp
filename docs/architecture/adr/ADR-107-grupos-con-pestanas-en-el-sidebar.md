# ADR-107 — Grupos con pestañas en el sidebar: Inventario pasa de 13 entradas a 5

Fecha: 2026-09-23
Estado: aceptada

## Contexto

El sidebar de Inventario tenía trece entradas (Stock, Requerimientos,
Traslados, Guías de remisión, Conteos, Artículos, Categorías, Unidades de
medida, Lotes, Ajustes, Devoluciones, Mermas, Reservas). Cada una es una
pantalla legítima, pero leídas en fila no dicen qué se hace dónde: para
encontrar "Mermas" había que recorrer la lista entera.

## Decisión

1. `ItemSubmenu` (`frontend/lib/navegacion.ts`) gana un campo opcional
   `pestanas`: pantallas hermanas que comparten **una** entrada del sidebar
   y se alternan con pestañas arriba del contenido. El `href` del grupo es el
   de su primera pestaña.
2. Inventario queda en cinco entradas, agrupadas por la pregunta que
   responden:

   | Entrada | Pestañas |
   |---|---|
   | Stock | Stock · Lotes · Reservas |
   | Requerimientos | — |
   | Movimientos | Traslados · Ajustes · Mermas · Devoluciones · Guías de remisión |
   | Conteos | — |
   | Maestros | Artículos · Categorías · Unidades de medida |

3. **Las URLs no cambian.** Cada pestaña sigue siendo su propia ruta, así que
   no se rompe ningún enlace, favorito, destino de notificación ni e2e.
4. Las pestañas las dibuja el shell (`PestanasSeccion` en `ModuloShell`) según
   la ruta; ninguna página las declara. Un módulo sin grupos queda igual.
5. La paleta de comandos y el rastro abren los grupos (`pantallasDe`): cada
   pestaña se sigue buscando por su nombre y el rastro dice "Inventario ›
   Lotes", no "Inventario › Stock".

## Alternativas descartadas

- **Fusionar pantallas en una sola página con estado interno**: rompía URLs y
  obligaba a reescribir trece páginas que ya funcionan.
- **Sidebar con encabezados de sección colapsables**: seguía mostrando trece
  enlaces; el problema era la cantidad, no el orden.

## Consecuencias

- Otros módulos pueden agrupar igual con solo tocar `navegacion.ts`.
- Una pestaña nueva se agrega al grupo; si no, no aparece en ningún lado
  (lo cubre `navegacion.test.ts`).
