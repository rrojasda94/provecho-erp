import { Insignia } from "@/components/estado/insignia";
import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

type Opcion = {
  id: string;
  tipo: string;
  nombre: string;
  costo: string;
  plazo_dias: number;
  puntaje_total: string;
};
type Evaluacion = {
  id: string;
  campana_id: string;
  objetivo: string;
  presupuesto_referencia: string;
  estado: string;
  opcion_elegida_id: string | null;
  motivo: string | null;
  opciones: Opcion[];
};
type Campana = { id: string; nombre: string };

const TONO: Record<string, "exito" | "alerta" | "neutro"> = {
  decidida: "exito",
  evaluada: "alerta",
  borrador: "neutro",
};

/**
 * Las evaluaciones de agencia, de todas las campañas.
 *
 * Se listaban **solo por campaña**, así que revisar «qué hay para decidir»
 * obligaba a recorrer campaña por campaña — y quien decide (Gerencia) no entra
 * por la campaña, entra por la decisión pendiente. Se ven las opciones con su
 * puntaje ponderado, que es lo que sostiene la decisión.
 */
export default async function AgenciasPage({
  searchParams,
}: {
  searchParams: Promise<{ estado?: string }>;
}) {
  const { token } = await obtenerSesion();
  const { estado = "" } = await searchParams;

  const query = new URLSearchParams({ page_size: "100" });
  if (estado) query.set("estado", estado);

  let pagina: Pagina<Evaluacion>;
  try {
    pagina = await apiFetch<Pagina<Evaluacion>>(
      `/api/v1/marketing/evaluaciones-agencia?${query}`,
      { token },
    );
  } catch (e) {
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para ver las evaluaciones de agencia."
          : "No se pudieron cargar las evaluaciones."}
      </p>
    );
  }

  const campanas = await apiFetch<Pagina<Campana>>(
    "/api/v1/marketing/campanas?page_size=100",
    { token },
  )
    .then((p) => p.items)
    .catch(() => [] as Campana[]);
  const nombre = new Map(campanas.map((c) => [c.id, c.nombre] as const));

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl text-dark">Evaluación de agencias</h1>
      <p className="text-sm text-gray">
        Contra qué se comparó cada propuesta y con qué puntaje. Los criterios y
        sus pesos se congelan al abrir la evaluación: cambiarlos después de ver
        las propuestas es elegir primero y justificar después.
      </p>

      {pagina.items.length === 0 ? (
        <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
          No hay evaluaciones registradas.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {pagina.items.map((ev) => (
            <article key={ev.id} className="flex flex-col gap-2 rounded border border-gray/30 p-4">
              <header className="flex flex-wrap items-baseline gap-2">
                <h2 className="font-heading text-base text-dark">{ev.objetivo}</h2>
                <span className="text-xs text-gray">
                  {nombre.get(ev.campana_id) ?? "campaña"}
                </span>
                <Insignia tono={TONO[ev.estado] ?? "neutro"}>{ev.estado}</Insignia>
                <span className="ml-auto text-sm">
                  referencia <span className="cifra">S/ {ev.presupuesto_referencia}</span>
                </span>
              </header>

              {ev.opciones.length === 0 ? (
                <p className="text-sm text-secondary">
                  Sin opciones cargadas: no hay contra qué comparar todavía.
                </p>
              ) : (
                <ul className="flex flex-col gap-1 text-sm">
                  {ev.opciones.map((o) => (
                    <li
                      key={o.id}
                      className="flex flex-wrap items-center gap-x-4 border-b border-gray/15 py-1.5"
                    >
                      <span className="font-semibold text-dark">{o.nombre}</span>
                      <span className="text-xs text-gray">{o.tipo}</span>
                      <span className="cifra">S/ {o.costo}</span>
                      <span className="cifra text-gray">{o.plazo_dias} días</span>
                      <span className="cifra font-semibold">{o.puntaje_total} pts</span>
                      {/* La elegida se marca sola: sin esto hay que cruzar
                          ids a ojo para saber cuál ganó. */}
                      {ev.opcion_elegida_id === o.id && (
                        <Insignia tono="exito">elegida</Insignia>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              {ev.motivo && (
                <p className="text-xs text-secondary">
                  <strong>Motivo de apartarse de la recomendada:</strong> {ev.motivo}
                </p>
              )}
            </article>
          ))}
        </div>
      )}

      <p className="text-xs text-gray">
        Cargar opciones y firmar la decisión siguen siendo por API: la decisión
        la firma Gerencia con el motivo obligatorio cuando se aparta de la
        recomendada, y eso pide su propia pantalla.
      </p>
    </div>
  );
}
