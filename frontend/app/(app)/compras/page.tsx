import { redirect } from "next/navigation";

import { MODULOS } from "@/lib/modulos";

/** La raíz del módulo no era una ruta y `/compras` daba 404 — ver
 * `app/(app)/catalogo/page.tsx` para el motivo completo. */
export default function ComprasRaiz() {
  redirect(MODULOS.find((m) => m.clave === "compras")!.href);
}
