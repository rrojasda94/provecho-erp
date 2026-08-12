import { ApiError, apiFetch } from "@/lib/api";
import { primeroElDe } from "@/lib/destinos";
import { obtenerSesion } from "@/lib/sesion";

import { CajaCliente, type Pos, type Sucursal, type Turno } from "./caja-cliente";

type FilaCaja = {
  caja: string;
  horas_abierta: number;
  monto_apertura: string;
  efectivo_cobrado: string;
  movimientos_netos: string;
  efectivo_esperado: string;
  diferencia_apertura: string | null;
};

type DatosOut = { filas: Record<string, unknown>[] };

function Monto({ valor }: { valor: string | null }) {
  return <span className="tabular-nums">S/ {valor ?? "0.00"}</span>;
}

export default async function CajaPage({
  searchParams,
}: {
  searchParams: Promise<{ cierre?: string }>;
}) {
  const { token } = await obtenerSesion();
  // `?cierre=<id>` es a donde llega `accounting.cierre_caja_irregular`: el
  // turno con el descuadre sube al tope de los cerrados (ADR-036).
  const { cierre } = await searchParams;

  let filas: FilaCaja[];
  try {
    // El reporte del catálogo (ADR-024) ya resuelve rótulo, horas abiertas y
    // efectivo esperado; repetir ese cálculo acá sería una segunda fuente de
    // verdad del mismo número.
    const datos = await apiFetch<DatosOut>("/api/v1/reportes/estado_caja/datos", {
      token,
      metodo: "POST",
      cuerpo: { preset: "hoy" },
    });
    filas = datos.filas as unknown as FilaCaja[];
  } catch (e) {
    const mensaje =
      e instanceof ApiError && e.status === 403
        ? "Tu usuario no tiene permiso para ver el estado de caja."
        : "No se pudo cargar el estado de caja.";
    return <p className="text-secondary">{mensaje}</p>;
  }

  // Sin `.catch(() => [])`: un listado que falla y se dibuja vacío dice
  // "no hay turnos cerrados" cuando lo que pasó es que la consulta reventó,
  // y eso se descubre el día que alguien busca un faltante y no lo encuentra.
  let turnos: Turno[];
  let pos: Pos[];
  let sucursales: Sucursal[];
  try {
    [turnos, pos, sucursales] = await Promise.all([
      apiFetch<Turno[]>("/api/v1/accounting/cajas/turnos", { token }),
      apiFetch<Pos[]>("/api/v1/accounting/pos-tarjeta", { token }),
      apiFetch<Sucursal[]>("/api/v1/sucursales", { token }),
    ]);
  } catch (e) {
    return (
      <p className="text-secondary">
        {e instanceof ApiError && e.status === 403
          ? "Tu usuario no tiene permiso para ver los turnos de caja."
          : "No se pudieron cargar los turnos de caja."}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl text-dark">Caja</h1>
      <p className="text-sm text-gray">
        Turnos abiertos ahora mismo, el que lleva más tiempo primero. El esperado es
        apertura + cobrado en efectivo + ingresos − retiros: es contra ese número que
        cuadra el cierre.
      </p>
      {filas.length === 0 ? (
        <p className="rounded bg-cream px-3 py-2 text-sm text-gray">
          Ninguna caja abierta. Se abren desde el PDV al iniciar el turno.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[46rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
                <th className="py-2 pr-4 font-semibold">Caja</th>
                <th className="py-2 pr-4 font-semibold">Horas abierta</th>
                <th className="py-2 pr-4 font-semibold">Apertura</th>
                <th className="py-2 pr-4 font-semibold">Cobrado</th>
                <th className="py-2 pr-4 font-semibold">Ingresos − retiros</th>
                <th className="py-2 pr-4 font-semibold">Esperado</th>
                <th className="py-2 font-semibold">Dif. al abrir</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((f, i) => (
                <tr key={`${f.caja}-${i}`} className="border-b border-gray/15">
                  <td className="py-2 pr-4 font-semibold text-dark">{f.caja}</td>
                  <td className="py-2 pr-4 tabular-nums">
                    {/* 12 h abiertas casi siempre significa que nadie cerró el
                        turno, no un turno largo. */}
                    <span className={Number(f.horas_abierta) >= 12 ? "text-secondary" : ""}>
                      {f.horas_abierta}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    <Monto valor={f.monto_apertura} />
                  </td>
                  <td className="py-2 pr-4">
                    <Monto valor={f.efectivo_cobrado} />
                  </td>
                  <td className="py-2 pr-4">
                    <Monto valor={f.movimientos_netos} />
                  </td>
                  <td className="py-2 pr-4 font-semibold">
                    <Monto valor={f.efectivo_esperado} />
                  </td>
                  <td className="py-2">
                    {f.diferencia_apertura ? (
                      <span className="font-semibold text-secondary">
                        <Monto valor={f.diferencia_apertura} />
                      </span>
                    ) : (
                      <span className="text-gray">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-gray">
        Abrir y cerrar el turno se hacen desde el PDV, en el terminal del cajero: es donde
        está el cajón que se cuenta.
      </p>

      <CajaCliente
        turnos={primeroElDe(turnos, cierre ?? null, (t) => t.cierre_id)}
        pos={pos}
        sucursales={sucursales}
      />
    </div>
  );
}
