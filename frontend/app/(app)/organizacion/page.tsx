import { redirect } from "next/navigation";

import { MODULOS } from "@/lib/modulos";

/** La raíz del módulo no era una ruta y `/organizacion` daba 404 — ver
 * `app/(app)/catalogo/page.tsx` para el motivo completo. */
export default function OrganizacionRaiz() {
  redirect(MODULOS.find((m) => m.clave === "organizacion")!.href);
}
