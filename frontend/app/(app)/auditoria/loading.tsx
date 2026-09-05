import { EsqueletoPantalla } from "@/components/estado/esqueleto-pantalla";

/** Silueta mientras el servidor resuelve la pantalla. Ver el componente:
 * un `loading.tsx` por módulo es lo que hace que el clic en el sidebar
 * acuse recibo en vez de parecer que la aplicación se colgó. */
export default function Cargando() {
  return <EsqueletoPantalla />;
}
