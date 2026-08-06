import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { UsuariosCliente, type Rol, type Usuario } from "./usuarios-cliente";

export default async function UsuariosPage() {
  const { token } = await obtenerSesion();

  try {
    const [usuarios, roles] = await Promise.all([
      apiFetch<Pagina<Usuario>>("/api/v1/users", { token }),
      apiFetch<Rol[]>("/api/v1/roles", { token }),
    ]);
    // Los roles de cada cuenta llegan por cuenta: `UsuarioOut` no los trae y
    // meterlos ahí obligaría a una consulta por fila en el backend igual.
    // Son decenas de usuarios, no miles; cuando lo sean, esto pasa a ser un
    // campo del listado.
    const rolesPorUsuario = Object.fromEntries(
      await Promise.all(
        usuarios.items.map(async (u) => [
          u.id,
          await apiFetch<Rol[]>(`/api/v1/users/${u.id}/roles`, { token }),
        ]),
      ),
    );
    return (
      <UsuariosCliente
        usuarios={usuarios.items}
        roles={roles}
        rolesPorUsuario={rolesPorUsuario}
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
