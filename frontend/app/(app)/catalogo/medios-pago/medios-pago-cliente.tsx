"use client";

import { useRef, useState } from "react";

import { catalogoApi, type MedioDePago } from "@/lib/catalogo";
import { ErrorApi } from "@/lib/cliente-api";
import { aTitulo } from "@/lib/texto";

/** Vocabulario de `medio_pago.tipo` (`rules.TIPOS_MEDIO_PAGO`). El tipo no
 * es cosmética: `efectivo` es el único con cajón detrás —da vuelto y entra a
 * la cadena de custodia (RN-MDP-002)— y `credito_empresarial` el único que
 * puede cotizar contra otra lista de precios (RN-MDP-001). */
const TIPOS = [
  {
    valor: "efectivo",
    etiqueta: "Efectivo",
    ayuda: "Da vuelto y entra al arqueo de caja.",
  },
  { valor: "billetera_digital", etiqueta: "Billetera digital", ayuda: "Yape, Plin." },
  { valor: "tarjeta_debito", etiqueta: "Tarjeta de débito", ayuda: "" },
  { valor: "tarjeta_credito", etiqueta: "Tarjeta de crédito", ayuda: "" },
  { valor: "transferencia", etiqueta: "Transferencia", ayuda: "" },
  { valor: "cheque", etiqueta: "Cheque", ayuda: "" },
  {
    valor: "credito_empresarial",
    etiqueta: "Crédito empresarial",
    ayuda: "Se factura y se cobra después (RN-MDP-001).",
  },
];

const DIRECCIONES = [
  { valor: "cobro", etiqueta: "Cobro", ayuda: "Aparece en el PDV." },
  { valor: "pago", etiqueta: "Pago", ayuda: "Con lo que se le paga a un tercero." },
  { valor: "ambos", etiqueta: "Ambos", ayuda: "" },
];

/**
 * Los medios de pago de la empresa: con qué se cobra en caja.
 *
 * Existían solo por API, y el resultado fue que en un entorno recién
 * levantado el PDV no ofrecía ninguno, no daba vuelto y el cobro salía sin
 * `medio_pago_id`. El seeder ya deja tres; acá se administran.
 *
 * **No hay borrar**: un medio que ya cobró no se puede quitar sin dejar
 * cobros huérfanos. Se apaga —sale del PDV y sigue nombrando lo suyo en el
 * histórico—, el mismo criterio que descontinuar un producto.
 */
export function MediosPagoCliente({ inicial }: { inicial: MedioDePago[] }) {
  const [medios, setMedios] = useState(inicial);
  const [error, setError] = useState("");

  async function editar(
    medio: MedioDePago,
    cuerpo: Partial<{
      nombre: string;
      tipo: string;
      comision_pct: string;
      activo: boolean;
    }>,
  ) {
    setError("");
    try {
      const guardado = await catalogoApi.editarMedioPago(medio.id, cuerpo);
      setMedios((lista) => lista.map((m) => (m.id === guardado.id ? guardado : m)));
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo guardar el cambio.");
    }
  }

  const cobrables = medios.filter(
    (m) => m.activo && (m.direccion === "cobro" || m.direccion === "ambos"),
  );

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-xl text-dark">Medios de pago</h1>
          <p className="text-xs text-gray">
            Con qué se cobra en caja. La comisión es informativa: no se le
            descuenta al cliente ni al total de la venta.
          </p>
        </div>
        <NuevoMedio
          onCreado={(m) =>
            setMedios((lista) =>
              [...lista, m].sort((a, b) => a.nombre.localeCompare(b.nombre)),
            )
          }
        />
      </div>

      {error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {error}
        </p>
      )}

      {/* Sin ninguno activo de cobro el PDV no puede cerrar una venta, y eso
          se descubre recién en la caja: acá se dice antes. */}
      {medios.length > 0 && cobrables.length === 0 && (
        <p
          role="alert"
          className="rounded-lg border border-secondary/40 bg-secondary/5 p-3 text-sm text-secondary"
        >
          Ningún medio activo para cobrar: el PDV no puede cerrar una venta
          hasta que haya al menos uno.
        </p>
      )}

      {medios.length === 0 ? (
        <p className="rounded-lg border border-dashed border-gray/30 p-6 text-center text-sm text-gray">
          Todavía no hay medios de pago. Crea el primero —normalmente
          Efectivo— para poder cobrar.
        </p>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-gray">
            <tr>
              <th className="py-1">Nombre</th>
              <th className="py-1 w-52">Tipo</th>
              <th className="py-1 w-24">Se usa en</th>
              <th className="py-1 w-28">Comisión %</th>
              <th className="py-1 w-20">Activo</th>
            </tr>
          </thead>
          <tbody>
            {medios.map((medio) => (
              <tr
                key={medio.id}
                className={`border-t border-gray/20 ${medio.activo ? "" : "text-gray"}`}
              >
                <td className="py-2 pr-2">
                  <input
                    defaultValue={medio.nombre}
                    className="w-full font-semibold"
                    maxLength={50}
                    aria-label={`Nombre de ${medio.nombre}`}
                    onBlur={(e) => {
                      const nombre = aTitulo(e.target.value);
                      e.target.value = nombre;
                      if (nombre && nombre !== medio.nombre) editar(medio, { nombre });
                    }}
                  />
                </td>
                <td className="py-2 pr-2">
                  <select
                    defaultValue={medio.tipo}
                    className="w-full text-sm"
                    aria-label={`Tipo de ${medio.nombre}`}
                    onChange={(e) => editar(medio, { tipo: e.target.value })}
                  >
                    {TIPOS.map((t) => (
                      <option key={t.valor} value={t.valor} title={t.ayuda}>
                        {t.etiqueta}
                      </option>
                    ))}
                  </select>
                </td>
                {/* `direccion` no se edita: de qué lado del mostrador se usa
                    un medio no es una corrección, es otro medio. */}
                <td className="py-2 pr-2 text-xs uppercase text-gray">
                  {DIRECCIONES.find((d) => d.valor === medio.direccion)?.etiqueta ??
                    medio.direccion}
                </td>
                <td className="py-2 pr-2">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    defaultValue={medio.comision_pct}
                    className="w-20"
                    aria-label={`Comisión de ${medio.nombre}`}
                    onBlur={(e) => {
                      const comision_pct = e.target.value;
                      if (comision_pct && comision_pct !== medio.comision_pct) {
                        editar(medio, { comision_pct });
                      }
                    }}
                  />
                </td>
                <td className="py-2">
                  <input
                    type="checkbox"
                    checked={medio.activo}
                    aria-label={`Activo: ${medio.nombre}`}
                    title="Apagado sale del PDV; los cobros que ya lo nombran no se tocan"
                    onChange={(e) => editar(medio, { activo: e.target.checked })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function NuevoMedio({ onCreado }: { onCreado: (medio: MedioDePago) => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState("efectivo");
  const [direccion, setDireccion] = useState("cobro");
  const [comision, setComision] = useState("0");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function crear() {
    setError("");
    setGuardando(true);
    try {
      onCreado(
        await catalogoApi.crearMedioPago({
          nombre,
          tipo,
          direccion,
          comision_pct: comision || "0",
        }),
      );
      setNombre("");
      setTipo("efectivo");
      setDireccion("cobro");
      setComision("0");
      dialogRef.current?.close();
    } catch (e) {
      setError(
        e instanceof ErrorApi ? e.message : "No se pudo crear el medio de pago.",
      );
    } finally {
      setGuardando(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => dialogRef.current?.showModal()}
        className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary"
      >
        + Nuevo medio de pago
      </button>
      <dialog
        ref={dialogRef}
        className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40"
      >
        <div className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg text-dark">Nuevo medio de pago</h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Nombre
            <input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              onBlur={() => setNombre((n) => aTitulo(n))}
              maxLength={50}
              placeholder="Yape"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Tipo
            <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
              {TIPOS.map((t) => (
                <option key={t.valor} value={t.valor} title={t.ayuda}>
                  {t.etiqueta}
                </option>
              ))}
            </select>
            <span className="text-xs font-normal text-gray">
              {TIPOS.find((t) => t.valor === tipo)?.ayuda}
            </span>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Se usa en
            <select value={direccion} onChange={(e) => setDireccion(e.target.value)}>
              {DIRECCIONES.map((d) => (
                <option key={d.valor} value={d.valor}>
                  {d.etiqueta}
                </option>
              ))}
            </select>
            <span className="text-xs font-normal text-gray">
              Solo los de cobro (y ambos) aparecen en el PDV.
            </span>
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Comisión %
            <input
              type="number"
              step="0.01"
              min="0"
              max="100"
              value={comision}
              onChange={(e) => setComision(e.target.value)}
              className="w-24"
            />
          </label>
          {error && (
            <p role="alert" className="text-sm font-semibold text-secondary">
              {error}
            </p>
          )}
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dialogRef.current?.close()}
              className="rounded border border-gray px-4 py-2 text-sm font-semibold text-dark"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={crear}
              disabled={guardando || !nombre.trim()}
              className="rounded bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-secondary disabled:opacity-50"
            >
              {guardando ? "Creando..." : "Crear"}
            </button>
          </div>
        </div>
      </dialog>
    </>
  );
}
