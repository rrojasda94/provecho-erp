/**
 * PWA del repartidor propio (ADR-098). Pantalla completa fuera del shell,
 * igual que el PDV y el KDS (ADR-013): se opera en la calle, con el
 * teléfono en una mano y la moto en la otra.
 *
 * El servidor resuelve sesión y permiso; las rutas vivas, el GPS y las
 * acciones sobre cada parada viven en el cliente — ver `reparto-cliente.tsx`,
 * `use-gps.ts` y `use-wake-lock.ts`.
 */

import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { type RutaConParadas } from "@/lib/delivery";
import { tienePermiso } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

import RepartoCliente from "./reparto-cliente";
import "./reparto.css";

export const metadata: Metadata = {
  title: "Mi reparto | Provecho",
  manifest: "/reparto/manifest.webmanifest",
};

function Bloqueo({ titulo, detalle }: { titulo: string; detalle: string }) {
  return (
    <main className="reparto-vacio">
      <h1>{titulo}</h1>
      <p>{detalle}</p>
    </main>
  );
}

export default async function PaginaReparto() {
  const { token, usuario } = await obtenerSesion();

  if (!tienePermiso(usuario.permisos, "delivery.repartir")) {
    return (
      <Bloqueo
        titulo="Sin permiso"
        detalle="Tu usuario no está dado de alta como repartidor. Pídele a un administrador el permiso `delivery.repartir`."
      />
    );
  }

  let rutas: RutaConParadas[];
  try {
    rutas = await apiFetch<RutaConParadas[]>("/api/v1/delivery/mi/rutas", { token });
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect("/login");
    return (
      <Bloqueo
        titulo="No se pudo cargar tu reparto"
        detalle="Revisa la conexión con la API e intenta de nuevo."
      />
    );
  }

  return <RepartoCliente inicial={rutas} />;
}
