import type { ConfigMapas } from "@/components/direccion/config-mapas";

/**
 * Configuración de Google Maps leída del entorno del proceso de Next.
 *
 * Solo se puede llamar desde el servidor (layout, páginas, Server Actions):
 * `process.env` no existe en el navegador y estas variables no son
 * `NEXT_PUBLIC_*` a propósito — se hornearían en el build.
 *
 * Sin `GOOGLE_MAPS_BROWSER_KEY` devuelve la clave vacía, que es lo que hace
 * que los campos de dirección queden como el `<input>` de texto de siempre.
 */
export function configMapas(): ConfigMapas {
  return {
    apiKey: process.env.GOOGLE_MAPS_BROWSER_KEY ?? "",
    // `DEMO_MAP_ID` es el identificador que Google publica para desarrollo:
    // el pin no se dibuja sin un Map ID, y pedir uno de la consola antes de
    // poder ver la pantalla funcionando sería un paso de más.
    mapId: process.env.GOOGLE_MAPS_MAP_ID || "DEMO_MAP_ID",
    pais: process.env.GOOGLE_MAPS_PAIS || "pe",
  };
}
