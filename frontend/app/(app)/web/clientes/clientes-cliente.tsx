"use client";

import { useState, useTransition } from "react";

import { restablecerClaveClienteAction } from "../actions";

export type ClienteWeb = {
  id: string;
  email: string;
  nombres: string;
  apellidos: string;
  telefono: string | null;
  numero_documento: string | null;
  tiene_password: boolean;
  tiene_google: boolean;
  debe_cambiar_clave: boolean;
  created_at: string;
};

type Resultado = { id: string; clave: string } | { id: string; error: string };

function Acceso({ cliente }: { cliente: ClienteWeb }) {
  const vias = [cliente.tiene_password && "Clave", cliente.tiene_google && "Google"];
  return (
    <>
      {vias.filter(Boolean).join(" + ") || "—"}
      {cliente.debe_cambiar_clave && (
        <span className="ml-2 rounded bg-cream px-1.5 py-0.5 font-semibold text-secondary">
          debe cambiar su clave
        </span>
      )}
    </>
  );
}

function PanelResultado({ resultado }: { resultado: Resultado | null }) {
  if (!resultado) return null;
  if ("error" in resultado) {
    return <p className="mb-2 text-xs text-secondary">{resultado.error}</p>;
  }
  return (
    <div className="mb-2 rounded border-2 border-accent bg-cream p-2 text-sm">
      <p>
        Clave temporal: <strong className="font-mono text-base">{resultado.clave}</strong>
      </p>
      <p className="text-xs text-gray">
        Dícetela al cliente ahora: no se vuelve a mostrar. Al ingresar tendrá que elegir una propia.
      </p>
      <button
        type="button"
        onClick={() => navigator.clipboard?.writeText(resultado.clave)}
        className="mt-1 text-xs font-bold text-primary hover:underline"
      >
        Copiar
      </button>
    </div>
  );
}

function Confirmacion({
  pendiente,
  onSi,
  onNo,
}: {
  pendiente: boolean;
  onSi: () => void;
  onNo: () => void;
}) {
  return (
    <div className="flex flex-col gap-1 text-xs">
      <span>Su clave actual dejará de funcionar y se cerrarán sus sesiones abiertas.</span>
      <div className="flex gap-3">
        <button
          type="button"
          disabled={pendiente}
          onClick={onSi}
          className="font-bold text-secondary hover:underline disabled:opacity-60"
        >
          {pendiente ? "Restableciendo..." : "Sí, restablecer"}
        </button>
        <button type="button" onClick={onNo} className="text-gray hover:underline">
          Cancelar
        </button>
      </div>
    </div>
  );
}

function Fila({
  cliente,
  resultado,
  onResultado,
}: {
  cliente: ClienteWeb;
  resultado: Resultado | null;
  onResultado: (r: Resultado) => void;
}) {
  const [confirmando, setConfirmando] = useState(false);
  const [pendiente, iniciar] = useTransition();

  function restablecer() {
    iniciar(async () => {
      const r = await restablecerClaveClienteAction(cliente.id);
      onResultado(r.ok ? { id: cliente.id, clave: r.clave } : { id: cliente.id, error: r.error });
      setConfirmando(false);
    });
  }

  return (
    <tr className="border-b border-border align-top">
      <td className="py-2 pr-3">
        <p className="font-semibold text-dark">
          {cliente.nombres} {cliente.apellidos}
        </p>
        <p className="text-xs text-gray">{cliente.email}</p>
      </td>
      <td className="py-2 pr-3 text-sm">{cliente.telefono ?? "—"}</td>
      <td className="py-2 pr-3 text-xs text-gray">
        <Acceso cliente={cliente} />
      </td>
      <td className="py-2">
        <PanelResultado resultado={resultado} />
        {confirmando ? (
          <Confirmacion
            pendiente={pendiente}
            onSi={restablecer}
            onNo={() => setConfirmando(false)}
          />
        ) : (
          <button
            type="button"
            onClick={() => setConfirmando(true)}
            className="text-xs font-bold text-primary hover:underline"
          >
            Restablecer clave
          </button>
        )}
      </td>
    </tr>
  );
}

export function ClientesCliente({
  clientes,
  busqueda,
  correoConfigurado = true,
}: {
  clientes: ClienteWeb[];
  busqueda: string;
  /** `false` = el servidor no tiene SMTP y ningún correo sale. */
  correoConfigurado?: boolean;
}) {
  const [resultado, setResultado] = useState<Resultado | null>(null);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-heading text-xl italic uppercase text-dark">Clientes del sitio web</h1>
        <p className="text-sm text-gray">
          Cuentas creadas en charlies.majambo.com.pe. Si un cliente no puede recuperar su clave por
          correo, restablécesela aquí y díctasela por teléfono.
        </p>
      </div>

      {!correoConfigurado && (
        <p className="rounded border border-secondary bg-cream px-3 py-2 text-sm text-dark">
          <strong>El servidor no está enviando correos.</strong> Falta configurar el correo
          saliente (<code>SMTP_*</code>), así que el enlace de &quot;olvidé mi contraseña&quot; no
          le llega a nadie. Mientras tanto, restablece la clave desde acá y díctala por teléfono.
        </p>
      )}

      <form method="get" className="flex gap-2">
        <input
          name="q"
          defaultValue={busqueda}
          placeholder="Buscar por nombre, email, teléfono o DNI"
          className="flex-1 text-sm"
        />
        <button
          type="submit"
          className="rounded border border-border px-3 py-1 text-sm font-bold hover:bg-cream"
        >
          Buscar
        </button>
      </form>

      {clientes.length === 0 ? (
        <p className="text-sm text-gray">No hay cuentas que coincidan.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card p-4">
          <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase text-gray">
                <th className="py-2 pr-3 font-semibold">Cliente</th>
                <th className="py-2 pr-3 font-semibold">Teléfono</th>
                <th className="py-2 pr-3 font-semibold">Cómo entra</th>
                <th className="py-2 font-semibold"></th>
              </tr>
            </thead>
            <tbody>
              {clientes.map((c) => (
                <Fila
                  key={c.id}
                  cliente={c}
                  resultado={resultado && resultado.id === c.id ? resultado : null}
                  onResultado={setResultado}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
