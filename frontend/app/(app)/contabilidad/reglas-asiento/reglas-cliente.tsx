"use client";

import { useState } from "react";

import { DialogoFormulario } from "@/components/formulario/dialogo-formulario";
import { Combobox } from "@/components/ui/combobox";
import { tienePermiso } from "@/lib/permisos";

import type { Cuenta } from "../asientos-cliente";
import { crearReglaAction } from "./actions";

export type Regla = {
  id: string;
  evento: string;
  cuenta_debe_id: string;
  cuenta_haber_id: string;
  activa: boolean;
};

/** Los eventos que hoy generan un asiento. Salen de las plantillas de fábrica
 * del PCGE (`domain/plantillas.py`): configurar una regla para un evento que
 * nadie publica sería configuración muda, y adivinar el nombre exacto del
 * evento a mano es la forma más fácil de escribir una regla que no se aplica
 * nunca. */
const EVENTOS = [
  { valor: "sales.venta_confirmada", etiqueta: "Venta confirmada" },
  { valor: "sales.comprobante_emitido", etiqueta: "Comprobante de venta emitido (IGV)" },
  { valor: "purchases.compra_recibida", etiqueta: "Compra recibida" },
  {
    valor: "purchases.comprobante_conforme",
    etiqueta: "Comprobante de compra conforme (IGV)",
  },
  { valor: "accounting.pago_ejecutado", etiqueta: "Pago a proveedor ejecutado" },
  { valor: "inventory.merma_registrada", etiqueta: "Merma desechada" },
  { valor: "inventory.transferencia_recibida", etiqueta: "Traslado recibido con faltante" },
  {
    valor: "inventory.consumo_personal_valorizado",
    etiqueta: "Comida del personal",
  },
];

const ADMINISTRAR = "accounting.cuenta_administrar";

function DialogoNuevaRegla({ cuentas }: { cuentas: Cuenta[] }) {
  const [debe, setDebe] = useState("");
  const [haber, setHaber] = useState("");
  const opciones = cuentas
    .filter((c) => c.activa)
    .map((c) => ({ valor: c.id, etiqueta: `${c.codigo} · ${c.nombre}` }));

  return (
    <DialogoFormulario
      titulo="Nueva regla de asiento"
      disparador="+ Nueva regla"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearReglaAction}
      ayuda="La regla escribe un asiento de dos líneas y reemplaza a la plantilla de fábrica para ese evento. Si el asiento oficial de ese hecho lleva más de dos líneas, la plantilla es mejor."
      alAbrir={() => {
        setDebe("");
        setHaber("");
      }}
    >
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Evento
        <select name="evento" defaultValue={EVENTOS[0].valor}>
          {EVENTOS.map((e) => (
            <option key={e.valor} value={e.valor}>
              {e.etiqueta}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cuenta del debe
        <Combobox
          name="cuenta_debe_id"
          etiqueta="Cuenta del debe"
          requerido
          marcador="Elegir cuenta..."
          value={debe}
          alCambiar={(v) => setDebe(v ?? "")}
          opciones={opciones}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Cuenta del haber
        <Combobox
          name="cuenta_haber_id"
          etiqueta="Cuenta del haber"
          requerido
          marcador="Elegir cuenta..."
          value={haber}
          alCambiar={(v) => setHaber(v ?? "")}
          opciones={opciones}
        />
      </label>
    </DialogoFormulario>
  );
}

export function ReglasCliente({
  reglas,
  cuentas,
  permisos,
}: {
  reglas: Regla[];
  cuentas: Cuenta[];
  permisos: string[];
}) {
  const nombre = new Map(cuentas.map((c) => [c.id, `${c.codigo} · ${c.nombre}`] as const));
  const etiqueta = new Map(EVENTOS.map((e) => [e.valor, e.etiqueta] as const));
  const configurados = new Set(reglas.filter((r) => r.activa).map((r) => r.evento));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="font-heading text-xl text-dark">Reglas de asiento</h1>
        {tienePermiso(permisos, ADMINISTRAR) && <DialogoNuevaRegla cuentas={cuentas} />}
      </div>
      <p className="text-sm text-gray">
        Con qué cuentas se asienta cada hecho del ERP. Sin regla, se usa la
        plantilla oficial del PCGE, que es el asiento peruano completo — con su
        IGV y su asiento de destino. Una regla lo reemplaza por uno de dos
        líneas: la empresa manda, pero conviene saber qué se está cambiando.
      </p>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[42rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray/30 text-left text-xs uppercase text-gray">
              <th className="py-2 pr-4 font-semibold">Hecho</th>
              <th className="py-2 pr-4 font-semibold">Debe</th>
              <th className="py-2 font-semibold">Haber</th>
            </tr>
          </thead>
          <tbody>
            {EVENTOS.map((e) => {
              const regla = reglas.find((r) => r.evento === e.valor && r.activa);
              return (
                <tr key={e.valor} className="border-b border-gray/15">
                  <td className="py-2 pr-4 font-semibold text-dark">{e.etiqueta}</td>
                  {regla ? (
                    <>
                      <td className="py-2 pr-4">
                        {nombre.get(regla.cuenta_debe_id) ?? regla.cuenta_debe_id}
                      </td>
                      <td className="py-2">
                        {nombre.get(regla.cuenta_haber_id) ?? regla.cuenta_haber_id}
                      </td>
                    </>
                  ) : (
                    <td colSpan={2} className="py-2 text-gray">
                      plantilla del PCGE
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Una regla para un evento que ya no existe no se aplica nunca y nadie
          se entera: se lista aparte en vez de esconderla. */}
      {reglas.some((r) => r.activa && !etiqueta.has(r.evento)) && (
        <div className="rounded border border-status-warning/40 bg-status-warning/10 px-4 py-3">
          <p className="text-sm font-semibold text-foreground">
            Reglas para eventos que el ERP no publica
          </p>
          <ul className="mt-1 flex flex-col gap-0.5 text-xs text-muted-foreground">
            {reglas
              .filter((r) => r.activa && !etiqueta.has(r.evento))
              .map((r) => (
                <li key={r.id} className="cifra">
                  {r.evento}
                </li>
              ))}
          </ul>
        </div>
      )}

      {configurados.size === 0 && (
        <p className="text-xs text-gray">
          Ninguna regla configurada: todo se asienta con las plantillas de fábrica,
          que es lo esperable salvo que el contador pida otra cosa.
        </p>
      )}
    </div>
  );
}
