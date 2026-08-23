import { redirect } from "next/navigation";

import { MODULOS } from "@/lib/modulos";

/**
 * La raíz del módulo era una carpeta sin ruta: `/catalogo` daba 404 aunque el
 * módulo existiera entero debajo. Nadie lo enlaza desde el shell —el ícono y
 * el rastro apuntan a la primera pantalla— pero sí lo teclea quien recorta la
 * URL para "subir un nivel", que es exactamente lo que uno hace cuando se
 * pierde.
 *
 * El destino sale de `lib/modulos.ts` en vez de repetirse acá: la primera
 * pantalla de un módulo cambia, y dos lugares donde declararla son dos
 * lugares donde puede quedar mal.
 */
export default function CatalogoRaiz() {
  redirect(MODULOS.find((m) => m.clave === "catalogo")!.href);
}
