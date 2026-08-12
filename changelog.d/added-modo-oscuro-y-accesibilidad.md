- **Modo oscuro y preferencias de accesibilidad, guardadas en el perfil**
  (ADR-037). Cierra el catálogo que `docs/product/ui-ux.md` dejó especificado
  en julio con hex exactos y nunca se implementó: paleta de alto contraste
  para daltonismo rojo-verde (Okabe-Ito, ~95% de los casos), escala de letra
  en cuatro niveles y modo oscuro. Las tres viven en `usuario`, no en el
  navegador, porque el documento es explícito y el motivo es operativo: en un
  local la misma tablet la usan tres turnos y la misma persona salta de la
  caja a la oficina; guardadas en el dispositivo hay que reconfigurarlas en
  cada máquina, que en la práctica significa no usarlas. Nuevo endpoint
  `PATCH /users/me/preferencias`, **sin permiso**: no hay privilegio que
  otorgar en elegir el tamaño de la propia letra, y pedir uno dejaría la
  accesibilidad fuera del alcance de quien más la necesita.
- Se resuelven **en el servidor**: el layout raíz escribe `class="dark"`,
  `data-escala` y `data-paleta` en `<html>`. No se usa `next-themes` —aunque
  ya estuviera instalado alimentando a `sonner`— porque guarda en
  `localStorage` y necesita un script inline antes del primer pintado, y la
  CSP de `middleware.ts` firma cada script con un nonce por request. Costo
  aceptado: no hay opción "seguir al sistema" (detectarla exige justo ese
  script) y cada cambio es un viaje al servidor.
- **Paleta y tema se combinan**, como pedía ui-ux.md: hay un bloque
  `.dark[data-paleta="alto-contraste"]` con la paleta Okabe-Ito aclarada —sus
  valores están medidos contra blanco y sobre `#101216` el azul cae a 3.6:1—.
  El orden importa: declarado antes del bloque oscuro, el tema apagaba la
  paleta accesible.
- **`Insignia` ata el ícono al tono**, que es lo que hace cumplible la regla
  de que ningún estado se comunique solo por color. Antes «activa» e
  «inactiva» eran la misma píldora gris para quien no distingue rojo de verde.
  De paso, un pago pendiente deja de mostrarse en rojo: no es un error, es
  plata que todavía se puede detener, y se leía igual que uno rechazado.
- **`Ctrl+K` abre cualquier pantalla del ERP** (cierra F2.29, que estaba «sin
  decidir»). Llegar a Plan de cuentas eran tres clics; ahora son cinco teclas.
  Sin dependencias nuevas: `@base-ui/react` Autocomplete + Dialog. `cmdk`
  traería un motor de coincidencia difusa para ~50 entradas estáticas y
  arrastra el árbol de Radix que ADR-013 descartó. Cada resultado es un enlace
  de verdad, así que Enter, clic central y «abrir en pestaña nueva» funcionan
  sin programarlos, y los destinos llegan filtrados por permiso.
- **Esqueletos de carga por módulo** (cierra F2.31, que decía «el dashboard
  hoy no tiene ni loading skeleton»). Sin `loading.tsx` Next espera a que el
  `page.tsx` resuelva y recién ahí pinta: el clic en el sidebar no acusa
  recibo y se lee como que la aplicación se colgó.
- **Ayuda contextual por campo de formulario** (`CampoFormulario`), pendiente
  escrito en ui-ux.md desde julio: quien carga un proveedor no tiene por qué
  saber que "condición de pago" se cuenta en días desde la recepción.
