/**
 * Punto de venta. El servidor solo resuelve la sesión y el contexto
 * (empresa, sucursal, punto de venta); toda la interacción vive en el
 * cliente, porque el PDV se opera a golpes de dedo y no puede pagar un
 * round-trip de renderizado por cada producto que se toca.
 */

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { COOKIE_TOKEN, decodificarClaims } from "@/lib/auth";

import PdvCliente from "./pdv-cliente";
import "./pdv.css";

type PuntoVenta = {
  id: string;
  sucursal_id: string;
  canal: string;
  serie_boleta: string;
  serie_factura: string;
  modalidades_habilitadas: string[] | null;
  politica_pago: string;
};

/** Cada motivo de bloqueo es un mensaje accionable, no un 500 genérico: el
 * cajero tiene que saber a quién pedirle qué. */
function Bloqueo({ titulo, detalle }: { titulo: string; detalle: string }) {
  return (
    <main className="pdv-vacio">
      <h1>{titulo}</h1>
      <p>{detalle}</p>
    </main>
  );
}

type Contexto =
  | { ok: true; sucursalId: string; empresaId: string | null; punto: PuntoVenta }
  | { ok: false; titulo: string; detalle: string };

async function resolverContexto(token: string): Promise<Contexto> {
  const claims = decodificarClaims(token);
  const sucursalId = claims?.sucursales?.[0];
  if (!claims || !sucursalId) {
    return {
      ok: false,
      titulo: "Sin sucursal asignada",
      detalle:
        "Tu usuario no tiene ninguna sucursal asignada, así que no hay caja que abrir. Pídele a un administrador que te asigne una.",
    };
  }

  let puntos: PuntoVenta[];
  try {
    puntos = await apiFetch<PuntoVenta[]>(
      `/api/v1/sales/puntos-venta?sucursal_id=${sucursalId}`,
      { token },
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect("/login");
    return {
      ok: false,
      titulo: "No se pudo cargar el punto de venta",
      detalle: "Revisa la conexión con la API e intenta de nuevo.",
    };
  }

  // El PDV atiende desde una caja física: canal `trabajador`. Los canales
  // `web`/`kiosko` son clientes del mismo contrato, no de esta pantalla.
  const punto = puntos.find((p) => p.canal === "trabajador") ?? puntos[0];
  if (!punto) {
    return {
      ok: false,
      titulo: "La sucursal no tiene puntos de venta",
      detalle:
        "Configura al menos una caja para esta sucursal antes de abrir el punto de venta.",
    };
  }
  return { ok: true, sucursalId, empresaId: claims.empresa_id, punto };
}

export default async function PaginaPdv() {
  const token = (await cookies()).get(COOKIE_TOKEN)?.value;
  if (!token) redirect("/login");

  const ctx = await resolverContexto(token);
  if (!ctx.ok) return <Bloqueo titulo={ctx.titulo} detalle={ctx.detalle} />;

  return (
    <PdvCliente
      empresaId={ctx.empresaId}
      sucursalId={ctx.sucursalId}
      puntoVenta={{
        id: ctx.punto.id,
        serieBoleta: ctx.punto.serie_boleta,
        serieFactura: ctx.punto.serie_factura,
        modalidades: ctx.punto.modalidades_habilitadas ?? [
          "mesa",
          "takeout",
          "delivery",
        ],
      }}
    />
  );
}
