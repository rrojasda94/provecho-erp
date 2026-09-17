/// <reference types="google.maps" />
/**
 * Carga del SDK de Google Maps, una sola vez por pestaña. Copia recortada
 * de `frontend/lib/google-maps.ts` — solo la librería `marker`, sin
 * `places` ni `geocoding` porque este sitio no tiene campo de dirección
 * (ADR-101, el mapa de locales solo dibuja marcadores fijos).
 *
 * El fix del race de `importLibrary` (ADR-080 §"Lo que apareció construyendo
 * esto") aplica igual acá: `window.google.maps` puede existir antes de que
 * `importLibrary` esté definido bajo `loading=async`.
 */

const ID = "google-maps-sdk";
const SONDEO_MS = 50;
const ESPERA_MAXIMA_MS = 10_000;

let promesa: Promise<typeof google.maps> | null = null;

function listo(): typeof google.maps | null {
  const maps = window.google?.maps;
  return typeof maps?.importLibrary === "function" ? maps : null;
}

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
      script.src =
        `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}` +
        "&libraries=marker&v=weekly&loading=async";
      script.async = true;
      script.onerror = () => rechazar(new Error("no se pudo cargar el SDK de Maps"));
      document.head.appendChild(script);
    }

    const inicio = Date.now();
    const sondear = () => {
      const maps = listo();
      if (maps) {
        resolver(maps);
        return;
      }
      if (Date.now() - inicio > ESPERA_MAXIMA_MS) {
        rechazar(new Error("tiempo de espera agotado cargando el SDK de Maps"));
        return;
      }
      setTimeout(sondear, SONDEO_MS);
    };
    sondear();
  });

  return promesa;
}
