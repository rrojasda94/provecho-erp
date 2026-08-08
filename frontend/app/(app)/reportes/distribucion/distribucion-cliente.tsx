"use client";

import { useMemo, useState } from "react";

import {
  CLASE_NIVEL,
  etiquetaAmbito,
  type Area,
  type MatrizFila,
  type MatrizRegla,
} from "@/lib/reports";

/**
 * El hub: qué reporta el ERP y a quién le llega.
 *
 * Los **huecos** y las **fugas** van arriba y en rojo a propósito. Una matriz
 * que solo muestra lo configurado se ve completa siempre; lo que un
 * administrador necesita ver es lo que falta.
 */

function Destinatarios({ regla }: { regla: MatrizRegla }) {
  if (regla.destinatarios.length === 0) {
    return <span className="text-sm text-secondary">— sin destinatarios —</span>;
  }
  return (
    <ul className="flex flex-wrap gap-1">
      {regla.destinatarios.map((d, i) => (
        <li
          key={`${d.tipo}-${d.id ?? d.etiqueta}-${i}`}
          className="rounded bg-gray/15 px-2 py-0.5 text-xs"
          title={`Destinatario por ${d.tipo}`}
        >
          <span className="font-semibold">{d.tipo}</span> · {d.etiqueta}
        </li>
      ))}
    </ul>
  );
}

function Regla({ regla }: { regla: MatrizRegla }) {
  return (
    <div className="flex flex-col gap-1 border-l-2 border-gray/30 pl-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-semibold">{regla.sucursal}</span>
        <span className={`rounded px-2 py-0.5 text-xs font-bold ${CLASE_NIVEL[regla.nivel] ?? ""}`}>
          {regla.nivel}
        </span>
        {!regla.activa ? (
          <span className="rounded bg-gray/15 px-2 py-0.5 text-xs">inactiva</span>
        ) : null}
        <span className="text-xs text-secondary">
          {regla.alcance} persona{regla.alcance === 1 ? "" : "s"}
          {regla.destinatarios.some((d) => d.tipo === "dinamico")
            ? " + los que resuelva el turno"
            : ""}
        </span>
        {regla.fuga ? (
          <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-bold text-red-900">
            fuga: no llega a nadie
          </span>
        ) : null}
      </div>
      <Destinatarios regla={regla} />
    </div>
  );
}

function Fila({ fila }: { fila: MatrizFila }) {
  return (
    <article className="flex flex-col gap-2 rounded border border-gray/30 p-4">
      <header className="flex flex-wrap items-baseline gap-2">
        <h2 className="font-bold">{fila.nombre}</h2>
        <code className="text-xs text-secondary">{fila.codigo}</code>
        <span className="rounded bg-gray/15 px-2 py-0.5 text-xs">
          {etiquetaAmbito(fila.ambito)}
        </span>
        <span className="rounded bg-gray/15 px-2 py-0.5 text-xs" title="Permiso del módulo dueño">
          {fila.permiso}
        </span>
        {fila.hueco ? (
          <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-bold text-red-900">
            hueco: ocurre y no se entera nadie
          </span>
        ) : null}
      </header>
      <p className="text-sm text-secondary">{fila.descripcion}</p>
      {fila.reglas.length === 0 ? (
        <p className="text-sm text-secondary">
          Sin reglas. Sugerido: {fila.areas_sugeridas.join(", ") || "—"}.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {fila.reglas.map((r) => (
            <Regla key={r.id} regla={r} />
          ))}
        </div>
      )}
    </article>
  );
}

export function DistribucionCliente({
  matriz,
  areas,
}: {
  matriz: MatrizFila[];
  areas: Area[];
}) {
  const [soloProblemas, setSoloProblemas] = useState(false);

  const problemas = useMemo(
    () => matriz.filter((f) => f.hueco || f.reglas.some((r) => r.fuga)),
    [matriz],
  );
  const visibles = soloProblemas ? problemas : matriz;

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-bold">Distribución de reportes</h1>
        <p className="text-sm text-secondary">
          Qué hechos del ERP generan un reporte y a qué áreas y usuarios llega cada uno.
          Las áreas configuradas son {areas.length || "—"}.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm">
          {matriz.length} emisiones · <strong>{problemas.length}</strong> con problemas
        </span>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={soloProblemas}
            onChange={(e) => setSoloProblemas(e.target.checked)}
          />
          Ver solo huecos y fugas
        </label>
      </div>

      {visibles.length === 0 ? (
        <p className="text-secondary">
          {soloProblemas
            ? "Ningún hueco ni fuga: todo hecho tiene a quién avisarle."
            : "No hay emisiones visibles para tu usuario."}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {visibles.map((f) => (
            <Fila key={f.codigo} fila={f} />
          ))}
        </div>
      )}
    </section>
  );
}
