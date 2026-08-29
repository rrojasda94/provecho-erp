"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Fragment, useState } from "react";

/** Los importes llegan como **string**, no como número: la API los serializa
 * desde `Decimal` y convertirlos a `number` en el sobre perdería céntimos en
 * cifras grandes. Se pasan a número recién al formatearlos. */
type Importe = string;

export type LineaEstado = { clave: string; etiqueta: string; monto: Importe };
export type SeccionEstado = {
  clave: string;
  etiqueta: string;
  naturaleza: string;
  lineas: LineaEstado[];
  total: Importe;
};
export type EstadoSituacion = {
  hasta: string | null;
  secciones: SeccionEstado[];
  total_activo: Importe;
  total_pasivo: Importe;
  total_patrimonio: Importe;
  total_pasivo_patrimonio: Importe;
  descuadre: Importe;
  cuadra: boolean;
  cuentas_sin_clasificar: string[];
};
export type EstadoResultados = {
  bloques: { clave: string; etiqueta: string; secciones: SeccionEstado[]; subtotal: Importe }[];
  resultado_ejercicio: Importe;
  resultado_libro: Importe;
  cuadra: boolean;
  cuentas_sin_clasificar: string[];
};
export type Balance = {
  cuentas: {
    codigo: string;
    nombre: string;
    tipo: string;
    debe: Importe;
    haber: Importe;
    saldo_deudor: Importe;
    saldo_acreedor: Importe;
  }[];
  total_debe: Importe;
  total_haber: Importe;
  cuadra: boolean;
};

const SOLES = new Intl.NumberFormat("es-PE", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Cero se dibuja como raya: una columna de "0.00" repetidos esconde las
 * pocas líneas que sí tienen movimiento, que es lo único que se viene a
 * mirar. */
function Monto({ valor, fuerte = false }: { valor: Importe; fuerte?: boolean }) {
  const n = Number(valor);
  return (
    <span
      className={`tabular-nums ${fuerte ? "font-bold text-dark" : ""} ${
        n < 0 ? "text-secondary" : ""
      }`}
    >
      {n === 0 ? "—" : SOLES.format(n)}
    </span>
  );
}

function Seccion({ seccion }: { seccion: SeccionEstado }) {
  return (
    <>
      <tr className="border-b border-gray/20 bg-gray/5">
        <th colSpan={2} className="py-1.5 pl-2 text-left text-xs uppercase text-gray">
          {seccion.etiqueta}
        </th>
      </tr>
      {seccion.lineas.map((linea) => (
        <tr key={linea.clave} className="border-b border-gray/10">
          <td className="py-1.5 pl-4 pr-4">{linea.etiqueta}</td>
          <td className="py-1.5 pr-2 text-right">
            <Monto valor={linea.monto} />
          </td>
        </tr>
      ))}
      <tr className="border-b border-gray/30">
        <td className="py-1.5 pl-4 pr-4 text-sm font-semibold text-dark">
          Total {seccion.etiqueta.toLowerCase()}
        </td>
        <td className="py-1.5 pr-2 text-right">
          <Monto valor={seccion.total} fuerte />
        </td>
      </tr>
    </>
  );
}

function Aviso({ cuadra, descuadre, sinClasificar }: {
  cuadra: boolean;
  descuadre?: Importe;
  sinClasificar: string[];
}) {
  if (cuadra && sinClasificar.length === 0) return null;
  return (
    <p role="alert" className="rounded border border-secondary/40 bg-secondary/5 p-3 text-sm">
      {!cuadra && (
        <strong className="text-secondary">
          El estado no cuadra
          {descuadre === undefined ? "" : ` por S/ ${SOLES.format(Number(descuadre))}`}.{" "}
        </strong>
      )}
      {sinClasificar.length > 0 && (
        <>
          Cuentas con saldo que ninguna línea del estado reclama:{" "}
          <span className="font-mono">{sinClasificar.join(", ")}</span>. Suelen ser cuentas
          creadas a mano con un código fuera del PCGE.
        </>
      )}
    </p>
  );
}

const PESTANAS = [
  { clave: "situacion", label: "Situación financiera" },
  { clave: "resultados", label: "Resultados" },
  { clave: "balance", label: "Balance de comprobación" },
] as const;

export function EstadosFinancierosCliente({
  desde,
  hasta,
  situacion,
  resultados,
  balance,
}: {
  desde: string;
  hasta: string;
  situacion: EstadoSituacion;
  resultados: EstadoResultados;
  balance: Balance;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [pestana, setPestana] = useState<(typeof PESTANAS)[number]["clave"]>("situacion");

  function cambiarRango(formData: FormData) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("desde", String(formData.get("desde") ?? desde));
    params.set("hasta", String(formData.get("hasta") ?? hasta));
    router.push(`/contabilidad/estados-financieros?${params.toString()}`);
  }

  const activo = situacion.secciones.filter((s) => s.clave.startsWith("activo"));
  const pasivoPatrimonio = situacion.secciones.filter((s) => !s.clave.startsWith("activo"));

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-xl text-dark">Estados financieros</h1>
      <p className="text-sm text-gray">
        Salen del libro contable, sin tabla de saldos intermedia: lo que se ve acá es la suma
        de los asientos registrados. El balance va <strong>a la fecha</strong> (acumulado) y
        el resultado <strong>al rango</strong>.
      </p>

      <form action={cambiarRango} className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Desde
          <input
            type="date"
            name="desde"
            defaultValue={desde}
            className="rounded border border-gray/40 px-2 py-1"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Hasta
          <input
            type="date"
            name="hasta"
            defaultValue={hasta}
            className="rounded border border-gray/40 px-2 py-1"
          />
        </label>
        <button
          type="submit"
          className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
        >
          Ver
        </button>
      </form>

      <nav className="flex gap-1 border-b border-gray/30">
        {PESTANAS.map((p) => (
          <button
            key={p.clave}
            type="button"
            onClick={() => setPestana(p.clave)}
            className={`px-3 py-2 text-sm font-semibold ${
              pestana === p.clave
                ? "border-b-2 border-primary text-dark"
                : "text-gray hover:text-dark"
            }`}
          >
            {p.label}
          </button>
        ))}
      </nav>

      {pestana === "situacion" && (
        <section className="flex flex-col gap-3">
          <Aviso
            cuadra={situacion.cuadra}
            descuadre={situacion.descuadre}
            sinClasificar={situacion.cuentas_sin_clasificar}
          />
          <div className="grid gap-6 md:grid-cols-2">
            <table className="w-full border-collapse text-sm">
              <tbody>
                {activo.map((s) => (
                  <Seccion key={s.clave} seccion={s} />
                ))}
                <tr className="border-t-2 border-dark">
                  <td className="py-2 pl-2 font-bold text-dark">TOTAL ACTIVO</td>
                  <td className="py-2 pr-2 text-right">
                    <Monto valor={situacion.total_activo} fuerte />
                  </td>
                </tr>
              </tbody>
            </table>
            <table className="w-full border-collapse text-sm">
              <tbody>
                {pasivoPatrimonio.map((s) => (
                  <Seccion key={s.clave} seccion={s} />
                ))}
                <tr className="border-t-2 border-dark">
                  <td className="py-2 pl-2 font-bold text-dark">TOTAL PASIVO Y PATRIMONIO</td>
                  <td className="py-2 pr-2 text-right">
                    <Monto valor={situacion.total_pasivo_patrimonio} fuerte />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}

      {pestana === "resultados" && (
        <section className="flex flex-col gap-3">
          <Aviso cuadra={resultados.cuadra} sinClasificar={resultados.cuentas_sin_clasificar} />
          <table className="w-full max-w-2xl border-collapse text-sm">
            <tbody>
              {resultados.bloques.map((bloque) => (
                <Fragment key={bloque.clave}>
                  {bloque.secciones.map((s) => (
                    <Seccion key={s.clave} seccion={s} />
                  ))}
                  <tr className="border-y-2 border-dark/60">
                    <td className="py-2 pl-2 font-bold text-dark">{bloque.etiqueta}</td>
                    <td className="py-2 pr-2 text-right">
                      <Monto valor={bloque.subtotal} fuerte />
                    </td>
                  </tr>
                </Fragment>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-gray">
            Presentación <strong>por naturaleza</strong>. La presentación por función (costo de
            ventas, gastos de venta y de administración) necesita los asientos de destino del
            PCGE —elemento 9 contra la 79— que el ERP todavía no genera.
          </p>
        </section>
      )}

      {pestana === "balance" && (
        <section className="flex flex-col gap-3">
          <Aviso cuadra={balance.cuadra} sinClasificar={[]} />
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
                <th className="py-2 pr-4 font-semibold">Cuenta</th>
                <th className="py-2 pr-4 text-right font-semibold">Debe</th>
                <th className="py-2 pr-4 text-right font-semibold">Haber</th>
                <th className="py-2 pr-4 text-right font-semibold">Saldo deudor</th>
                <th className="py-2 text-right font-semibold">Saldo acreedor</th>
              </tr>
            </thead>
            <tbody>
              {balance.cuentas.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-3 text-gray">
                    Ninguna cuenta tuvo movimiento en el rango.
                  </td>
                </tr>
              )}
              {balance.cuentas.map((c) => (
                <tr key={c.codigo} className="border-b border-gray/15">
                  <td className="py-1.5 pr-4">
                    <span className="font-mono text-xs text-gray">{c.codigo}</span> {c.nombre}
                  </td>
                  <td className="py-1.5 pr-4 text-right">
                    <Monto valor={c.debe} />
                  </td>
                  <td className="py-1.5 pr-4 text-right">
                    <Monto valor={c.haber} />
                  </td>
                  <td className="py-1.5 pr-4 text-right">
                    <Monto valor={c.saldo_deudor} />
                  </td>
                  <td className="py-1.5 text-right">
                    <Monto valor={c.saldo_acreedor} />
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-dark">
                <td className="py-2 font-bold text-dark">Totales</td>
                <td className="py-2 pr-4 text-right">
                  <Monto valor={balance.total_debe} fuerte />
                </td>
                <td className="py-2 pr-4 text-right">
                  <Monto valor={balance.total_haber} fuerte />
                </td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          </table>
        </section>
      )}
    </div>
  );
}
