import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Proveedor } from "../ordenes-compra/ordenes-compra-cliente";
import { FacturasCliente, type ComprobanteRecibido } from "./facturas-cliente";

type Params = Promise<{ proveedor?: string; desde?: string; hasta?: string; tipo?: string }>;

/** Tope del contrato (ADR-026). La tabla pagina en el navegador sobre lo que
 * recibe; el filtro por proveedor y por fecha es lo que la mantiene corta. */
const MAXIMO = 200;

/**
 * El registro de compras: qué facturas recibió la empresa.
 *
 * No existía ningún endpoint de lectura de comprobantes recibidos —el
 * `GET /sales/comprobantes` es de los emitidos—, así que una factura de
 * proveedor registrada solo se podía volver a ver entrando a la OC que la
 * sustenta, si uno se acordaba de cuál era.
 */
export default async function FacturasPage({ searchParams }: { searchParams: Params }) {
  const { token } = await obtenerSesion();
  const filtros = await searchParams;

  const query = new URLSearchParams({ page_size: String(MAXIMO) });
  const pares: [string, string | undefined][] = [
    ["proveedor_id", filtros.proveedor],
    ["desde", filtros.desde],
    ["hasta", filtros.hasta],
    ["tipo", filtros.tipo],
  ];
  for (const [clave, valor] of pares) if (valor) query.set(clave, valor);

  let pagina: Pagina<ComprobanteRecibido>;
  try {
    pagina = await apiFetch<Pagina<ComprobanteRecibido>>(
      `/api/v1/purchases/comprobantes?${query}`,
      { token },
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las facturas de proveedor."
        : "No se pudieron cargar las facturas.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  const proveedores = await apiFetch<Pagina<Proveedor>>(
    "/api/v1/purchases/proveedores?page_size=200",
    { token },
  )
    .then((p) => p.items)
    .catch(() => [] as Proveedor[]);

  return (
    <FacturasCliente
      facturas={pagina.items}
      total={pagina.total}
      recortado={pagina.total > pagina.items.length}
      proveedores={proveedores}
      filtros={{
        proveedor: filtros.proveedor ?? "",
        desde: filtros.desde ?? "",
        hasta: filtros.hasta ?? "",
      }}
    />
  );
}
