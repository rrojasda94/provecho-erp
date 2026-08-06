import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import { ParametrosCliente, type Divisa, type Parametro } from "./parametros-cliente";

export default async function ParametrosPage() {
  const { token, usuario } = await obtenerSesion();

  try {
    const [parametros, divisas] = await Promise.all([
      apiFetch<Parametro[]>("/api/v1/parametros", { token }),
      apiFetch<Divisa[]>("/api/v1/divisas", { token }),
    ]);
    return (
      <ParametrosCliente
        parametros={parametros}
        divisas={divisas}
        empresaId={usuario.empresa_id ?? ""}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Solo Gerencia ve la bandeja completa: hay parámetros sensibles (los rangos salariales de RRHH) que no son de lectura general."
        : "No se pudieron cargar los parámetros.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
