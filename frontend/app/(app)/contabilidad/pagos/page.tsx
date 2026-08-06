import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { PagosCliente, type Pago, type Proveedor } from "./pagos-cliente";

export default async function PagosPage() {
  const { token } = await obtenerSesion();

  let pagos: Pago[];
  try {
    pagos = (
      await apiFetch<Pagina<Pago>>("/api/v1/accounting/pagos-proveedor", { token })
    ).items;
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver la cola de pagos."
        : "No se pudo cargar la cola de pagos.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // Solo para poner nombre a quién se le paga. Un contador sin
  // `purchases.leer` sigue viendo la cola (con el id del proveedor), en vez
  // de que la pantalla entera caiga por un permiso que no es el suyo —
  // mismo criterio que Proveedores con las personas.
  let proveedores: Proveedor[] = [];
  try {
    proveedores = (
      await apiFetch<Pagina<Proveedor>>("/api/v1/purchases/proveedores", { token })
    ).items;
  } catch {
    // silencioso a propósito, ver comentario arriba.
  }

  return <PagosCliente pagos={pagos} proveedores={proveedores} />;
}
