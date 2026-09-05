import Link from "next/link";

import { ApiError, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/sesion";

import type { Cuenta } from "../asientos-cliente";
import { SelectorCuenta } from "./selector-cuenta";

type Movimiento = {
  fecha: string;
  asiento_id: string;
  glosa: string;
  estado: string;
  debe: string;
  haber: string;
  saldo: string;
};
type LibroMayor = {
  cuenta_id: string;
  desde: string | null;
  hasta: string | null;
  movimientos: Movimiento[];
  saldo_final: string;
};

function TablaMayor({ movimientos }: { movimientos: Movimiento[] }) {
  if (movimientos.length === 0) {
    return (
      <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
        Esta cuenta no tuvo movimientos en el rango elegido.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[44rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
            <th className="py-2 pr-4 font-semibold">Fecha</th>
            <th className="py-2 pr-4 font-semibold">Glosa</th>
            <th className="py-2 pr-4 text-right font-semibold">Debe</th>
            <th className="py-2 pr-4 text-right font-semibold">Haber</th>
            <th className="py-2 text-right font-semibold">Saldo</th>
          </tr>
        </thead>
        <tbody>
          {movimientos.map((m) => (
            <tr
              key={`${m.asiento_id}-${m.fecha}-${m.debe}-${m.haber}`}
              className="border-b border-gray/15"
            >
              <td className="py-2 pr-4 cifra">{m.fecha}</td>
              <td className="py-2 pr-4">
                {/* El asiento se abre desde acá: un movimiento raro se
                    entiende mirando las otras líneas del asiento, no esta
                    sola. */}
                <Link
                  href={`/contabilidad/asientos/${m.asiento_id}`}
                  className="font-semibold text-primary hover:underline"
                >
                  {m.glosa}
                </Link>
                {m.estado === "anulado" && (
                  <span className="ml-2 text-xs text-gray">(anulado)</span>
                )}
              </td>
              <td className="py-2 pr-4 text-right cifra">
                {Number(m.debe) > 0 ? m.debe : "—"}
              </td>
              <td className="py-2 pr-4 text-right cifra">
                {Number(m.haber) > 0 ? m.haber : "—"}
              </td>
              <td className="py-2 text-right cifra font-semibold">{m.saldo}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function sinPlanDeCuentas(e: unknown): string {
  return e instanceof ApiError && e.status === 403
    ? "Tu usuario no tiene permiso para ver el libro contable."
    : "No se pudo cargar el plan de cuentas.";
}

function Mayor({ libro, cuenta }: { libro: LibroMayor; cuenta: Cuenta | undefined }) {
  return (
    <>
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="font-heading text-lg italic uppercase text-dark">
          {cuenta ? `${cuenta.codigo} · ${cuenta.nombre}` : "Cuenta"}
        </h2>
        <p className="text-sm font-semibold text-dark">
          Saldo final: <span className="cifra">S/ {libro.saldo_final}</span>
        </p>
      </div>
      <TablaMayor movimientos={libro.movimientos} />
    </>
  );
}

/** El mayor pedido, o el motivo por el que no se pudo. Aparte de la página
 * para que el `try/catch` no engorde el componente. */
async function mayorDe(
  token: string,
  cuenta: string,
  desde: string | undefined,
  hasta: string | undefined,
): Promise<{ libro: LibroMayor | null; error: string }> {
  const query = new URLSearchParams({ cuenta_id: cuenta });
  if (desde) query.set("desde", desde);
  if (hasta) query.set("hasta", hasta);
  try {
    return {
      libro: await apiFetch<LibroMayor>(
        `/api/v1/accounting/reportes/libro-mayor?${query}`,
        { token },
      ),
      error: "",
    };
  } catch (e) {
    return {
      libro: null,
      error:
        e instanceof ApiError && e.status === 404
          ? "Esa cuenta no existe o está fuera de tu alcance."
          : "No se pudo cargar el mayor de la cuenta.",
    };
  }
}

/**
 * El mayor de una cuenta: qué la movió, en qué orden y cómo quedó el saldo.
 *
 * `GET /accounting/reportes/libro-mayor` existía y **no lo llamaba nadie**:
 * Estados financieros usa el balance de comprobación, que dice el saldo de
 * cada cuenta y no de dónde salió. Con un saldo raro no había forma de
 * abrirlo — la pregunta «¿por qué la 1212 tiene esto?» no se podía hacer.
 */
export default async function LibroMayorPage({
  searchParams,
}: {
  searchParams: Promise<{ cuenta?: string; desde?: string; hasta?: string }>;
}) {
  const { token } = await obtenerSesion();
  const { cuenta = "", desde = "", hasta = "" } = await searchParams;

  let cuentas: Cuenta[];
  try {
    cuentas = await apiFetch<Cuenta[]>("/api/v1/accounting/cuentas-contables", { token });
  } catch (e) {
    return <p className="text-secondary">{sinPlanDeCuentas(e)}</p>;
  }

  const { libro, error } = cuenta
    ? await mayorDe(token, cuenta, desde, hasta)
    : { libro: null, error: "" };

  const elegida = cuentas.find((c) => c.id === cuenta);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl text-dark">Libro mayor</h1>
      <p className="text-sm text-gray">
        Todo lo que movió una cuenta, en orden, con el saldo corriendo al lado. Es
        donde se contesta «¿por qué esta cuenta tiene este saldo?»: el balance dice
        cuánto, el mayor dice de dónde.
      </p>

      <SelectorCuenta cuentas={cuentas} cuenta={cuenta} desde={desde} hasta={hasta} />

      {error && <p className="text-sm font-semibold text-secondary">{error}</p>}

      {!cuenta && !error && (
        <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
          Elegí una cuenta para ver su mayor.
        </p>
      )}

      {libro && <Mayor libro={libro} cuenta={elegida} />}
    </div>
  );
}
