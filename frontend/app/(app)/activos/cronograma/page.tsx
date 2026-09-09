import { AlertTriangle, Calendar } from "lucide-react";
import Link from "next/link";

import { Insignia } from "@/components/estado/insignia";
import { Vacio } from "@/components/estado/vacio";
import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

type ItemCronograma = {
  tipo: "mantenimiento" | "documento";
  estado: "al_dia" | "proximo" | "vencido" | "renovado";
  fecha: string | null;
  km: number | null;
  nombre: string;
  activo_id: string | null;
  documento_id: string | null;
};

/**
 * La pregunta con la que se abre el módulo: "¿qué se me viene?", no "deme
 * la tabla de planes" — agenda unificada de mantenimientos y documentos
 * próximos/vencidos, ordenada por fecha (`GET /assets/cronograma`).
 */
export default async function CronogramaPage() {
  const { token } = await obtenerSesion();

  let items: ItemCronograma[];
  try {
    items = await apiFetch<ItemCronograma[]>("/api/v1/assets/cronograma?dias=90", { token });
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el cronograma de activos."
        : "No se pudo cargar el cronograma.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl text-dark">Cronograma</h1>
      {items.length === 0 ? (
        <Vacio
          titulo="Nada pendiente en los próximos 90 días"
          detalle="Los mantenimientos y documentos por vencer aparecerán aquí."
          Icono={Calendar}
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((item, i) => (
            <li
              key={i}
              className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3"
            >
              <div className="flex items-center gap-3">
                {item.tipo === "mantenimiento" ? (
                  <Calendar size={16} className="text-muted-foreground" aria-hidden />
                ) : (
                  <AlertTriangle size={16} className="text-muted-foreground" aria-hidden />
                )}
                <div>
                  <p className="font-medium text-foreground">{item.nombre}</p>
                  <p className="text-xs text-muted-foreground">
                    {item.tipo === "mantenimiento" ? "Mantenimiento" : "Documento"}
                    {item.fecha && ` · ${item.fecha}`}
                    {item.km != null && ` · ${item.km} km`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <EstadoInsignia estado={item.estado} />
                {item.tipo === "mantenimiento" && item.activo_id && (
                  <Link
                    href={`/activos/activos/${item.activo_id}`}
                    className="text-xs font-medium underline"
                  >
                    Ver activo
                  </Link>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EstadoInsignia({ estado }: { estado: ItemCronograma["estado"] }) {
  if (estado === "vencido") return <Insignia tono="peligro">Vencido</Insignia>;
  if (estado === "proximo") return <Insignia tono="alerta">Próximo</Insignia>;
  if (estado === "renovado") return <Insignia tono="neutro">Renovado</Insignia>;
  return <Insignia tono="exito">Al día</Insignia>;
}
