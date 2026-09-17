import { redirect } from "next/navigation";

import { MODULOS } from "@/lib/modulos";

/** La raíz del módulo no es una ruta — ver `catalogo/page.tsx` para el
 * motivo completo. */
export default function SupervisionRaiz() {
  redirect(MODULOS.find((m) => m.clave === "supervision")!.href);
}
