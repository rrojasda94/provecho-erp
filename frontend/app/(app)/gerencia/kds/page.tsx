import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import {
  KdsGerenciaCliente,
  type ConfiguracionKds,
  type PropuestaKds,
} from "./kds-cliente";

const CODIGOS = [
  "kds_minutos_ambar",
  "kds_minutos_rojo",
  "kds_color_normal",
  "kds_color_ambar",
  "kds_color_rojo",
];

/** Semáforo del KDS: a partir de qué minuto una tarjeta de cocina cambia de
 * color, y de qué color.
 *
 * Dos llamadas y no una, mismo criterio que `gerencia/delivery`:
 * `/kds/configuracion` dice con qué valores **está pintando** la cocina (lo
 * aprobado, o la semilla del módulo), y `/parametros` dice qué hay propuesto
 * y sin resolver. Mezclarlas mostraría un valor que nadie está usando.
 */
export default async function KdsGerenciaPage() {
  const { token, usuario } = await obtenerSesion();

  try {
    const [configuracion, parametros] = await Promise.all([
      apiFetch<ConfiguracionKds>("/api/v1/kds/configuracion", { token }),
      apiFetch<(PropuestaKds & { estado: string })[]>(
        "/api/v1/parametros?modulo=sales&estado=propuesto",
        { token },
      ),
    ]);
    return (
      <KdsGerenciaCliente
        configuracion={configuracion}
        pendientes={parametros.filter((p) => CODIGOS.includes(p.codigo))}
        empresaId={usuario.empresa_id ?? ""}
      />
    );
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Los tiempos del KDS los fija Gerencia: hacen falta los permisos de cocina y de parámetros."
        : "No se pudieron cargar los tiempos del KDS.";
    return <p className="text-secondary">{mensaje}</p>;
  }
}
