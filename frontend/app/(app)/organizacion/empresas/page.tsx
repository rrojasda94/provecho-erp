import { ApiError, apiFetch } from "@/lib/api";
import { esCuentaDeAdministracion } from "@/lib/permisos";
import { obtenerSesion } from "@/lib/sesion";

import { EmpresasCliente, type Empresa, type Grupo } from "./empresas-cliente";

export default async function EmpresasPage() {
  const { token, usuario } = await obtenerSesion();

  let empresas: Empresa[];
  try {
    empresas = await apiFetch<Empresa[]>("/api/v1/empresas", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver las empresas."
        : "No se pudieron cargar las empresas.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // El nombre del grupo es contexto, no el dato central: si este usuario no
  // lo puede leer, la tabla de empresas sigue viva mostrando su id — mismo
  // criterio que Proveedores con las personas.
  let grupos: Grupo[] = [];
  try {
    grupos = await apiFetch<Grupo[]>("/api/v1/grupos", { token });
  } catch {
    // silencioso a propósito, ver comentario arriba.
  }

  return (
    <EmpresasCliente
      empresas={empresas}
      grupos={grupos}
      esSuperusuario={esCuentaDeAdministracion(usuario)}
    />
  );
}
