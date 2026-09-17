import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

type Informe = {
  id: string;
  sucursal_id: string;
  fecha: string;
  total: number;
  completadas: number;
  vencidas: number;
  fotos_invalidas: number;
};

type Tarea = {
  id: string;
  nombre: string;
  momento: string;
  estado: "pendiente" | "completada" | "vencida";
  completada_at: string | null;
  asignado_a: string | null;
  tiene_foto: boolean;
  foto_valida: boolean | null;
};

function fotoTexto(tarea: Tarea): string {
  if (!tarea.tiene_foto) return "—";
  if (tarea.foto_valida === true) return "✓ válida";
  if (tarea.foto_valida === false) return "⚠️ fuera de ventana";
  return "sin fecha";
}

export default async function InformeDetallePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { token } = await obtenerSesion();
  const { id } = await params;

  let informe: Informe;
  try {
    informe = await apiFetch<Informe>(`/api/v1/supervision/informes/${id}`, { token });
  } catch (e) {
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para ver este informe."
          : "No se pudo cargar el informe."}
      </p>
    );
  }

  const tareas = await apiFetch<Tarea[]>(
    `/api/v1/supervision/tareas?sucursal_id=${informe.sucursal_id}&fecha=${informe.fecha}`,
    { token },
  ).catch(() => [] as Tarea[]);

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <h1 className="font-heading text-xl text-dark">Informe del {informe.fecha}</h1>
      <div className="flex gap-6 text-sm">
        <span>
          Total: <strong>{informe.total}</strong>
        </span>
        <span>
          Completadas: <strong>{informe.completadas}</strong>
        </span>
        <span>
          Vencidas: <strong>{informe.vencidas}</strong>
        </span>
        <span>
          Fotos a revisar: <strong>{informe.fotos_invalidas}</strong>
        </span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-[var(--sombra-1)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase text-gray">
              <th className="p-2">Tarea</th>
              <th className="p-2">Momento</th>
              <th className="p-2">Estado</th>
              <th className="p-2">Hora</th>
              <th className="p-2">Foto</th>
            </tr>
          </thead>
          <tbody>
            {tareas.map((t) => (
              <tr key={t.id} className="border-b border-border last:border-0">
                <td className="p-2">{t.nombre}</td>
                <td className="p-2">{t.momento}</td>
                <td className="p-2">{t.estado}</td>
                <td className="p-2">
                  {t.completada_at ? new Date(t.completada_at).toLocaleTimeString() : "—"}
                </td>
                <td className="p-2">{fotoTexto(t)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
