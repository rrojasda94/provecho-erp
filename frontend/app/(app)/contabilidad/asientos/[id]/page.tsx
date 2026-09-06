import Link from "next/link";

import { Insignia } from "@/components/estado/insignia";
import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Asiento, Cuenta } from "../../asientos-cliente";

type Linea = {
  id: string;
  cuenta_contable_id: string;
  tipo: string;
  monto: string;
};

/** La cabecera: de qué hecho salió y cómo está. Aparte de la página para no
 * pasarnos del límite de complejidad con puro JSX condicional. */
function FichaAsiento({ asiento }: { asiento: Asiento }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-2 rounded bg-cream px-4 py-3 text-sm sm:grid-cols-4">
      <div>
        <dt className="text-xs uppercase text-gray">Fecha</dt>
        <dd className="cifra font-semibold">{asiento.fecha}</dd>
      </div>
      <div>
        <dt className="text-xs uppercase text-gray">Origen</dt>
        <dd className="font-semibold">
          {asiento.origen === "automatico"
            ? (asiento.evento_origen ?? "automático")
            : "manual"}
        </dd>
      </div>
      {asiento.referencia_origen && (
        <div className="col-span-2">
          <dt className="text-xs uppercase text-gray">Documento que lo originó</dt>
          <dd className="cifra break-all">{asiento.referencia_origen}</dd>
        </div>
      )}
      {asiento.asiento_reversa_de_id && (
        <div className="col-span-2">
          <dt className="text-xs uppercase text-gray">Reversa de</dt>
          <dd>
            <Link
              href={`/contabilidad/asientos/${asiento.asiento_reversa_de_id}`}
              className="cifra break-all text-primary hover:underline"
            >
              {asiento.asiento_reversa_de_id}
            </Link>
          </dd>
        </div>
      )}
    </dl>
  );
}

function TablaLineas({
  lineas,
  nombre,
}: {
  lineas: Linea[];
  nombre: Map<string, string>;
}) {
  const total = (tipo: string) =>
    lineas.filter((l) => l.tipo === tipo).reduce((t, l) => t + Number(l.monto), 0);
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
            <th className="py-2 pr-4 font-semibold">Cuenta</th>
            <th className="py-2 pr-4 text-right font-semibold">Debe</th>
            <th className="py-2 text-right font-semibold">Haber</th>
          </tr>
        </thead>
        <tbody>
          {lineas.map((l) => (
            <tr key={l.id} className="border-b border-gray/15">
              <td className="py-2 pr-4">
                <Link
                  href={`/contabilidad/libro-mayor?cuenta=${l.cuenta_contable_id}`}
                  className="text-primary hover:underline"
                >
                  {nombre.get(l.cuenta_contable_id) ?? l.cuenta_contable_id}
                </Link>
              </td>
              <td className="py-2 pr-4 text-right cifra">
                {l.tipo === "debe" ? l.monto : "—"}
              </td>
              <td className="py-2 text-right cifra">
                {l.tipo === "haber" ? l.monto : "—"}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="font-semibold text-dark">
            <td className="py-2 pr-4">Totales</td>
            <td className="py-2 pr-4 text-right cifra">{total("debe").toFixed(2)}</td>
            <td className="py-2 text-right cifra">{total("haber").toFixed(2)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

/**
 * Las líneas de un asiento.
 *
 * `GET /asientos/{id}` y `/asientos/{id}/lineas` existían y **no los llamaba
 * nadie**: el listado de Asientos mostraba fecha, glosa, origen y estado, y
 * nunca contra qué cuentas se escribió. Un asiento automático que sale
 * raro no se podía revisar sin entrar a la base.
 */
export default async function AsientoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { token } = await obtenerSesion();

  let asiento: Asiento;
  let lineas: Linea[];
  let cuentas: Cuenta[];
  try {
    [asiento, lineas, cuentas] = await Promise.all([
      apiFetch<Asiento>(`/api/v1/accounting/asientos/${id}`, { token }),
      apiFetch<Linea[]>(`/api/v1/accounting/asientos/${id}/lineas`, { token }),
      apiFetch<Cuenta[]>("/api/v1/accounting/cuentas-contables", { token }),
    ]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      return <p className="text-secondary">Ese asiento no existe.</p>;
    }
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para ver el libro contable."
          : "No se pudo cargar el asiento."}
      </p>
    );
  }

  const nombre = new Map(cuentas.map((c) => [c.id, `${c.codigo} · ${c.nombre}`] as const));

  return (
    <div className="flex flex-col gap-4">
      <Link href="/contabilidad" className="text-sm font-semibold text-primary hover:underline">
        ← Asientos
      </Link>

      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="font-heading text-xl text-dark">{asiento.glosa}</h1>
        <Insignia tono={asiento.estado === "anulado" ? "neutro" : "exito"}>
          {asiento.estado}
        </Insignia>
      </div>

      <FichaAsiento asiento={asiento} />

      <TablaLineas lineas={lineas} nombre={nombre} />
    </div>
  );
}
