import { ApiError, apiFetch } from "@/lib/api";
import { tienePermiso } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

import { AlmacenesCliente, type Almacen, type Sucursal } from "./almacenes-cliente";

export default async function AlmacenesPage() {
  const { token, usuario } = await obtenerSesion();

  // Los almacenes dados de baja solo los ve —y los recupera— quien administra
  // la organización; la API responde 403 a cualquier otro que pida la
  // bandera, así que ni se la pedimos (F2.28: el gate visual no es la
  // autorización, es no provocar un 403 que rompería la pantalla entera).
  const puedeGestionar = tienePermiso(usuario.permisos, "organizacion.gestionar");
  const rutaAlmacenes = puedeGestionar
    ? "/api/v1/almacenes?incluir_baja=true"
    : "/api/v1/almacenes";

  let almacenes: Almacen[];
  let sucursales: Sucursal[];
  try {
    [almacenes, sucursales] = await Promise.all([
      apiFetch<Almacen[]>(rutaAlmacenes, { token }),
      apiFetch<Sucursal[]>("/api/v1/sucursales", { token }),
    ]);
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver los almacenes."
        : "No se pudieron cargar los almacenes.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return (
    <AlmacenesCliente
      almacenes={almacenes}
      sucursales={sucursales}
      puedeGestionar={puedeGestionar}
    />
  );
}
