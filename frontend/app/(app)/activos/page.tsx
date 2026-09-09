import { redirect } from "next/navigation";

import { MODULOS } from "@/lib/modulos";

/** La raíz del módulo no es una ruta — ver `app/(app)/catalogo/page.tsx`
 * para el motivo completo. */
export default function ActivosRaiz() {
  redirect(MODULOS.find((m) => m.clave === "activos")!.href);
}
