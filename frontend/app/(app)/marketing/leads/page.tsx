import { Insignia } from "@/components/estado/insignia";
import { ApiError, apiFetch, type Pagina } from "@/lib/api";
import { fecha } from "@/lib/fechas";
import { obtenerSesion } from "@/lib/sesion";

import { FiltroLeads } from "./filtro-leads";

type Lead = {
  id: string;
  campana_id: string;
  canal: string;
  tipo: string;
  contacto: string | null;
  cliente_id: string | null;
  venta_id: string | null;
  created_at: string;
};
type Campana = { id: string; nombre: string; estado: string };

/**
 * Las pistas que dejaron las campañas.
 *
 * `GET /campanas/{id}/leads` existía y obligaba a saber de antemano qué
 * campaña mirar; la pregunta que se hace de verdad es **«¿qué pistas quedaron
 * sin trabajar?»**, que cruza campañas. Ese listado no existía, así que un
 * lead sin atribuir era invisible salvo entrando campaña por campaña.
 */
export default async function LeadsPage({
  searchParams,
}: {
  searchParams: Promise<{ atribuido?: string; campana?: string }>;
}) {
  const { token } = await obtenerSesion();
  const { atribuido = "", campana = "" } = await searchParams;

  const query = new URLSearchParams({ page_size: "100" });
  if (atribuido) query.set("atribuido", atribuido);
  if (campana) query.set("campana_id", campana);

  let leads: Pagina<Lead>;
  try {
    leads = await apiFetch<Pagina<Lead>>(`/api/v1/marketing/leads?${query}`, { token });
  } catch (e) {
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para ver los leads."
          : "No se pudieron cargar los leads."}
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
      <h1 className="font-heading text-xl text-dark">Leads</h1>
      <p className="text-sm text-gray">
        Cada contacto, visita, cupón o registro que trajo una campaña. Un lead
        <strong> sin venta</strong> es una pista que todavía no se convirtió: son
        los que hay que trabajar, y son los que este listado deja ver por primera
        vez sin recorrer campaña por campaña.
      </p>

      <FiltroLeads atribuido={atribuido} campana={campana} campanas={campanas} />

      {leads.items.length === 0 ? (
        <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
          No hay leads con esos filtros.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[44rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
                <th className="py-2 pr-4 font-semibold">Cuándo</th>
                <th className="py-2 pr-4 font-semibold">Campaña</th>
                <th className="py-2 pr-4 font-semibold">Canal</th>
                <th className="py-2 pr-4 font-semibold">Tipo</th>
                <th className="py-2 pr-4 font-semibold">Contacto</th>
                <th className="py-2 font-semibold">Se convirtió</th>
              </tr>
            </thead>
            <tbody>
              {leads.items.map((l) => (
                <tr key={l.id} className="border-b border-gray/15">
                  <td className="py-2 pr-4 cifra">{fecha(l.created_at)}</td>
                  <td className="py-2 pr-4 font-semibold text-dark">
                    {nombre.get(l.campana_id) ?? "campaña"}
                  </td>
                  <td className="py-2 pr-4">{l.canal}</td>
                  <td className="py-2 pr-4">{l.tipo}</td>
                  <td className="py-2 pr-4">{l.contacto ?? "—"}</td>
                  <td className="py-2">
                    <Insignia tono={l.venta_id ? "exito" : "alerta"}>
                      {l.venta_id ? "sí" : "todavía no"}
                    </Insignia>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-gray">
        {leads.total} leads en total. La atribución a una venta la hace sola el
        cupón al cobrarse; a mano sigue siendo por API — hace falta un buscador
        de ventas que todavía no existe.
      </p>
    </div>
  );
}
