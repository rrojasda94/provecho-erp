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

// Con `loading=async` el evento `load` del `<script>` dispara en cuanto
// termina de descargarse el bootstrap, no cuando `google.maps` queda
// realmente utilizable: Google adjunta `importLibrary` un instante después,
// de forma asíncrona. Sin esta espera, `window.google.maps` existe pero es
// un objeto a medio armar —el `typeof` da "object" igual— y la primera
// llamada a `importLibrary` revienta con "no es una función", silenciada por
// el `.catch` de quien llama. Se sondea hasta que el método aparece.
const ESPERA_IMPORT_LIBRARY_MS = 20;
const TOPE_ESPERA_IMPORT_LIBRARY_MS = 4000;

function esperarImportLibrary(): Promise<typeof google.maps> {
  return new Promise((resolver, rechazar) => {
    const limite = Date.now() + TOPE_ESPERA_IMPORT_LIBRARY_MS;
    const intentar = () => {
      const maps = window.google?.maps;
      if (maps && typeof maps.importLibrary === "function") {
        resolver(maps);
        return;
      }
      if (Date.now() > limite) {
        rechazar(new Error("el SDK de Maps cargó incompleto"));
        return;
      }
      setTimeout(intentar, ESPERA_IMPORT_LIBRARY_MS);
    };
    intentar();
  });
}

let promesa: Promise<typeof google.maps> | null = null;

/**
 * Devuelve el namespace de Maps ya cargado, con `importLibrary` disponible.
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
    if (typeof window.google?.maps?.importLibrary === "function") {
      resolver(window.google.maps);
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
    script.addEventListener("load", () => {
      esperarImportLibrary().then(resolver, rechazar);
    });
    script.addEventListener("error", () =>
      rechazar(new Error("no se pudo cargar el SDK de Maps")),
    );
  });
  // Un fallo no puede dejar la promesa rechazada pegada al módulo: la
  // siguiente pantalla merece su propio intento (el usuario pudo recuperar
  // internet en el medio).
  promesa.catch(() => {
    promesa = null;
  });
  return promesa;
}
