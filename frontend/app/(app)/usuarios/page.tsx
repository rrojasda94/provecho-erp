import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  UsuariosCliente,
  type Rol,
  type Sucursal,
  type Usuario,
} from "./usuarios-cliente";

async function porUsuario<T>(
  usuarios: Usuario[],
  recurso: string,
  token: string,
): Promise<Record<string, T[]>> {
  return Object.fromEntries(
    await Promise.all(
      usuarios.map(async (u) => [
        u.id,
        await apiFetch<T[]>(`/api/v1/users/${u.id}/${recurso}`, { token }),
      ]),
    ),
  );
}

export default async function UsuariosPage() {
  const { token, usuario } = await obtenerSesion();

  try {
    const [usuarios, roles, sucursales] = await Promise.all([
      apiFetch<Pagina<Usuario>>("/api/v1/users", { token }),
      apiFetch<Rol[]>("/api/v1/roles", { token }),
      apiFetch<Sucursal[]>("/api/v1/sucursales", { token }),
    ]);
    // Los roles y las sucursales de cada cuenta llegan por cuenta:
    // `UsuarioOut` no los trae y meterlos ahí obligaría a una consulta por
    // fila en el backend igual. Son decenas de usuarios, no miles; cuando lo
    // sean, esto pasa a ser un campo del listado.
    const [rolesPorUsuario, sucursalesPorUsuario] = await Promise.all([
      porUsuario<Rol>(usuarios.items, "roles", token),
      porUsuario<Sucursal>(usuarios.items, "sucursales", token),
    ]);
    return (
      <UsuariosCliente
        usuarios={usuarios.items}
        roles={roles}
        rolesPorUsuario={rolesPorUsuario}
        sucursales={sucursales}
        sucursalesPorUsuario={sucursalesPorUsuario}
        permisos={usuario.permisos}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para administrar cuentas."
        : "No se pudo cargar la lista de cuentas.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
