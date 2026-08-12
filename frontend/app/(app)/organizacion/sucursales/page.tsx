import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  SucursalesCliente,
  type Almacen,
  type Marca,
  type Sucursal,
} from "./sucursales-cliente";

export default async function SucursalesPage() {
  const { token } = await obtenerSesion();

  let sucursales: Sucursal[];
  let marcas: Marca[];
  // Los almacenes viajan para poder decir de quién se abastece cada local: el
  // dato vive en `almacen` (el que se abastece es el almacén, no la sucursal)
  // pero se busca acá.
  let almacenes: Almacen[];
  try {
    [sucursales, marcas, almacenes] = await Promise.all([
      apiFetch<Sucursal[]>("/api/v1/sucursales", { token }),
      apiFetch<Marca[]>("/api/v1/marcas", { token }),
      apiFetch<Almacen[]>("/api/v1/almacenes", { token }),
    ]);
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las sucursales."
        : "No se pudieron cargar las sucursales.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return (
    <SucursalesCliente sucursales={sucursales} marcas={marcas} almacenes={almacenes} />
  );
}
