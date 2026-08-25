/**
 * Pad de marcación de asistencia. Pantalla completa fuera del shell, como
 * el PDV y el KDS (ADR-013): es una tablet colgada en el pasillo del local.
 *
 * La tablet queda logueada con la cuenta de servicio de la sucursal
 * (`terminal_asistencia`), que solo puede listar estos nombres y presentar
 * una marcación firmada. Quien marca es el trabajador, con su PIN
 * (ADR-065, RN-RRHH-020).
 */

import { redirect } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import type { Tarjeta } from "@/lib/asistencia";
import { tienePermiso } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

import TarjetasCliente from "./tarjetas-cliente";
import "./asistencia.css";

function Bloqueo({ titulo, detalle }: { titulo: string; detalle: string }) {
  return (
    <main className="asistencia-vacio">
      <h1>{titulo}</h1>
      <p>{detalle}</p>
    </main>
  );
}

export default async function PaginaAsistencia() {
  const { token, usuario } = await obtenerSesion();

  if (!tienePermiso(usuario.permisos, "rrhh.asistencia_terminal")) {
    return (
      <Bloqueo
        titulo="Sin permiso"
        detalle="Esta pantalla se abre con la cuenta del terminal del local. Pídele a un administrador que la configure."
      />
    );
  }

  const sucursalId = usuario.sucursales[0];
  if (!sucursalId) {
    return (
      <Bloqueo
        titulo="Sin sucursal asignada"
        detalle="La cuenta del terminal no tiene sucursal asignada, así que no hay a quién mostrar."
      />
    );
  }

  let tarjetas: Tarjeta[];
  try {
    tarjetas = await apiFetch<Tarjeta[]>(
      `/api/v1/rrhh/asistencia/terminal/tarjetas?sucursal_id=${sucursalId}`,
      { token },
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) redirect("/login");
    return (
      <Bloqueo
        titulo="No se pudo cargar el pad"
        detalle="Revisa la conexión con la API e intenta de nuevo."
      />
    );
  }

  return <TarjetasCliente sucursalId={sucursalId} inicial={tarjetas} />;
}
