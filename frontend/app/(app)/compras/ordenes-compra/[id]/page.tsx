import Link from "next/link";

import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Almacen, Articulo, OrdenCompra, Proveedor } from "../ordenes-compra-cliente";
import {
  OrdenCompraCliente,
  type Comprobante,
  type Recepcion,
} from "./orden-compra-cliente";

/**
 * La ficha de una orden de compra.
 *
 * No existía, y por eso la OC era «un ente aislado e inútil»: los endpoints
 * de emitir, recibir, anular y dar conformidad existen y están probados desde
 * el primer slice del módulo, pero el listado solo ofrecía «Editar» y solo en
 * `borrador`. Una OC emitida no tenía ninguna acción en ninguna pantalla.
 */
export default async function OrdenCompraPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { token, usuario } = await obtenerSesion();
  const { id } = await params;

  // La OC primero y sola: si no existe o no es de tu empresa, lo demás no
  // tiene por qué pedirse.
  let orden: OrdenCompra;
  try {
    orden = await apiFetch<OrdenCompra>(`/api/v1/purchases/ordenes-compra/${id}`, {
      token,
    });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 404
        ? "Esa orden de compra no existe o no es de tu empresa."
        : "No se pudo cargar la orden de compra.";
    return (
      <div className="flex flex-col gap-3">
        <p className="text-secondary">{mensaje}</p>
        <Link href="/compras/ordenes-compra" className="text-sm underline">
          Volver a Órdenes de compra
        </Link>
      </div>
    );
  }

  const [recepciones, comprobantes, proveedores, almacenes, articulos] = await Promise.all([
    apiFetch<Recepcion[]>(`/api/v1/purchases/ordenes-compra/${id}/recepciones`, {
      token,
    }).catch(() => [] as Recepcion[]),
    apiFetch<Comprobante[]>(`/api/v1/purchases/ordenes-compra/${id}/comprobantes`, {
      token,
    }).catch(() => [] as Comprobante[]),
    apiFetch<Pagina<Proveedor>>("/api/v1/purchases/proveedores?page_size=200", {
      token,
    })
      .then((p) => p.items)
      .catch(() => [] as Proveedor[]),
    apiFetch<Almacen[]>("/api/v1/almacenes", { token }).catch(() => [] as Almacen[]),
    // De otro módulo: si inventory niega, la ficha se dibuja igual y los
    // artículos salen por su id. Mismo criterio que el listado.
    apiFetch<Pagina<Articulo>>("/api/v1/inventory/articulos?page_size=200", { token })
      .then((p) => p.items)
      .catch(() => [] as Articulo[]),
  ]);

  return (
    <OrdenCompraCliente
      orden={orden}
      recepciones={recepciones}
      comprobantes={comprobantes}
      proveedor={proveedores.find((p) => p.id === orden.proveedor_id) ?? null}
      almacen={almacenes.find((a) => a.id === orden.almacen_destino_id)?.nombre ?? null}
      articulos={articulos}
      permisos={usuario.permisos}
    />
  );
}
