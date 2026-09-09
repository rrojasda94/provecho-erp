import Link from "next/link";

import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Activo } from "../activos-cliente";
import {
  FichaActivoCliente,
  type CargaCombustible,
  type ComprobanteDisponible,
  type Documento,
  type LecturaOdometro,
  type OrdenMantenimiento,
  type PlanMantenimiento,
  type RepuestoCompatible,
  type ResumenConsumo,
} from "./ficha-cliente";

export default async function FichaActivoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { token } = await obtenerSesion();
  const { id } = await params;

  let activo: Activo;
  try {
    activo = await apiFetch<Activo>(`/api/v1/assets/activos/${id}`, { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Ese activo no es de tu empresa."
        : "No se pudo cargar el activo.";
    return (
      <div className="flex flex-col gap-3">
        <p className="text-secondary">{mensaje}</p>
        <Link href="/activos/activos" className="text-sm underline">
          Volver a Activos
        </Link>
      </div>
    );
  }

  const esVehiculo = activo.tipo === "vehiculo";

  const [planes, ordenes, documentos, lecturas, cargas, consumo, comprobantes, repuestosCompatibles] =
    await Promise.all([
      apiFetch<PlanMantenimiento[]>(`/api/v1/assets/activos/${id}/planes`, { token }).catch(
        () => [] as PlanMantenimiento[],
      ),
      apiFetch<Pagina<OrdenMantenimiento>>(
        `/api/v1/assets/ordenes-mantenimiento?activo_id=${id}&page_size=100`,
        { token },
      )
        .then((p) => p.items)
        .catch(() => [] as OrdenMantenimiento[]),
      apiFetch<Documento[]>(
        `/api/v1/assets/documentos?sujeto_tipo=activo&sujeto_id=${id}`,
        { token },
      ).catch(() => [] as Documento[]),
      esVehiculo
        ? apiFetch<LecturaOdometro[]>(`/api/v1/assets/activos/${id}/lecturas-odometro`, {
            token,
          }).catch(() => [] as LecturaOdometro[])
        : Promise.resolve([] as LecturaOdometro[]),
      esVehiculo
        ? apiFetch<CargaCombustible[]>(`/api/v1/assets/activos/${id}/cargas-combustible`, {
            token,
          }).catch(() => [] as CargaCombustible[])
        : Promise.resolve([] as CargaCombustible[]),
      esVehiculo
        ? apiFetch<ResumenConsumo>(`/api/v1/assets/activos/${id}/consumo`, { token }).catch(
            () => null,
          )
        : Promise.resolve(null),
      esVehiculo
        ? apiFetch<ComprobanteDisponible[]>("/api/v1/assets/comprobantes-disponibles", {
            token,
          }).catch(() => [] as ComprobanteDisponible[])
        : Promise.resolve([] as ComprobanteDisponible[]),
      apiFetch<RepuestoCompatible[]>(`/api/v1/assets/activos/${id}/repuestos-compatibles`, {
        token,
      }).catch(() => [] as RepuestoCompatible[]),
    ]);

  return (
    <FichaActivoCliente
      activo={activo}
      planes={planes}
      ordenes={ordenes}
      documentos={documentos}
      lecturas={lecturas}
      cargas={cargas}
      consumo={consumo}
      comprobantesDisponibles={comprobantes}
      repuestosCompatibles={repuestosCompatibles}
    />
  );
}
