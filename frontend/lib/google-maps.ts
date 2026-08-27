/// <reference types="google.maps" />
/**
 * Carga del SDK de Google Maps, una sola vez por pestaña.
 *
 * El `<script>` se inserta desde JavaScript y no con `next/script` por la CSP:
 * `script-src` lleva `'strict-dynamic'`, que le da a un script ya autorizado
 * —el bundle de Next, que va con nonce— permiso para cargar los suyos. Un
 * `<script>` insertado así hereda esa confianza sin repetir el nonce.
 *
 * Memoizado en una promesa de módulo: cuatro campos de dirección en la misma
 * pantalla cargarían el SDK cuatro veces, y Google avisa por consola cuando
 * eso pasa.
 */

const ID = "google-maps-sdk";
const SONDEO_MS = 50;
/** Una conexión mala tarda; una clave rechazada no llega nunca. */
const ESPERA_MAXIMA_MS = 10_000;

let promesa: Promise<typeof google.maps> | null = null;

/**
 * El namespace, solo si ya sirve para algo.
 *
 * `window.google.maps` aparece **antes** de que el bootstrap de `loading=async`
 * termine de definir `importLibrary`, así que su sola presencia no es señal de
 * que el SDK esté listo: quien resolvía con eso recibía un namespace a medio
 * armar y moría con «maps.importLibrary is not a function» — dentro del
 * `.catch()` mudo de `CampoDireccion`, o sea sin ningún síntoma más que un
 * campo de texto pelado. `importLibrary` es lo único que le pedimos al SDK,
 * así que es también la condición honesta de «cargó».
 */
function listo(): typeof google.maps | null {
  const maps = window.google?.maps;
  return typeof maps?.importLibrary === "function" ? maps : null;
}

/**
 * Devuelve el namespace de Maps ya cargado.
 *
 * Rechaza si el script no llega: sin clave, sin internet o con la clave
 * restringida a otro dominio. Quien llama tiene que quedarse con el campo de
 * texto de siempre — nunca romper el formulario porque un tercero no
 * respondió (ADR-053).
 */
export function cargarMaps(apiKey: string): Promise<typeof google.maps> {
  if (promesa) return promesa;
  if (!apiKey) return Promise.reject(new Error("sin clave de Google Maps"));

  promesa = new Promise((resolver, rechazar) => {
    if (typeof window === "undefined") {
      rechazar(new Error("el SDK de Maps solo carga en el navegador"));
      return;
    }
    const yaEsta = listo();
    if (yaEsta) {
      resolver(yaEsta);
      return;
    }

    const existente = document.getElementById(ID) as HTMLScriptElement | null;
    const script = existente ?? document.createElement("script");
    if (!existente) {
      script.id = ID;
      // `loading=async` es lo que pide Google para no bloquear el render;
      // `v=weekly` fija el canal, no la versión: `beta` mueve el piso.
      script.src =
        `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}` +
        "&libraries=places,marker,geocoding&v=weekly&loading=async";
      script.async = true;
      document.head.appendChild(script);
    }
    // Se sondea en vez de escuchar `load`, por dos motivos que se dan a la
    // vez: `load` avisa de que el bootstrap corrió, no de que `importLibrary`
    // ya exista; y un `<script>` que YA terminó de cargar no vuelve a emitir
    // `load`, así que reusar el existente —lo que pasa en cada recarga en
    // caliente, porque `promesa` es del módulo y se reinicia con él— dejaba la
    // promesa esperando para siempre un evento que ya había ocurrido.
    let restan = Math.ceil(ESPERA_MAXIMA_MS / SONDEO_MS);
    const reloj = setInterval(() => {
      const maps = listo();
      if (maps) {
        clearInterval(reloj);
        resolver(maps);
      } else if (--restan <= 0) {
        clearInterval(reloj);
        rechazar(new Error("el SDK de Maps no terminó de cargar"));
      }
    }, SONDEO_MS);

    script.addEventListener("error", () => {
      clearInterval(reloj);
      rechazar(new Error("no se pudo cargar el SDK de Maps"));
    });
  });
  // Un fallo no puede dejar la promesa rechazada pegada al módulo: la
  // siguiente pantalla merece su propio intento (el usuario pudo recuperar
  // internet en el medio).
  promesa.catch(() => {
    promesa = null;
  });
  return promesa;
}
