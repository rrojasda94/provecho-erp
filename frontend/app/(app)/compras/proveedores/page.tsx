import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { ProveedoresCliente, type Persona, type Proveedor } from "./proveedores-cliente";

export default async function ProveedoresPage() {
  const { token } = await obtenerSesion();

  let proveedores: Proveedor[];
  try {
    proveedores = await apiFetch<Proveedor[]>("/api/v1/purchases/proveedores", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver proveedores."
        : "No se pudo cargar la lista de proveedores.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // Solo para resolver el nombre de los proveedores `natural` en la tabla —
  // si este usuario no tiene ni `personas.leer` ni `users.gestionar`, la
  // lista de proveedores sigue funcionando (los `natural` muestran su id
  // en vez del nombre, en vez de que toda la pantalla se caiga por un
  // permiso que no es el central de esta pantalla).
  let personas: Persona[] = [];
  try {
    personas = await apiFetch<Persona[]>("/api/v1/personas/buscar", { token });
  } catch {
    // silencioso a propósito, ver comentario arriba.
  }

  return <ProveedoresCliente proveedores={proveedores} personas={personas} />;
}
