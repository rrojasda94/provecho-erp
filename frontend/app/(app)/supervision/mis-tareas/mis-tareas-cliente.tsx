"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { Insignia } from "@/components/estado/insignia";

import { completarAction, marcarItemAction, subirFotoAction } from "./actions";

export type ChecklistItem = { texto: string; hecho: boolean };
export type TareaInstancia = {
  id: string;
  fecha: string;
  momento: "apertura" | "cierre";
  orden: number;
  nombre: string;
  requiere_foto: boolean;
  checklist: ChecklistItem[];
  estado: "pendiente" | "completada" | "vencida";
  tiene_foto: boolean;
  foto_valida: boolean | null;
  observacion: string | null;
};

function InsigniaEstado({ estado }: { estado: TareaInstancia["estado"] }) {
  if (estado === "completada") return <Insignia tono="exito">Completada</Insignia>;
  if (estado === "vencida") return <Insignia tono="peligro">Vencida</Insignia>;
  return <Insignia tono="neutro">Pendiente</Insignia>;
}

/**
 * Lo que ve un trabajador de línea al abrir el módulo: solo sus propias
 * tareas del día (`GET /tareas/mias`), agrupadas por momento y orden — dos
 * tareas con el mismo orden se hacen en paralelo (RN-SUP-002), así que se
 * muestran una junto a la otra y no en fila.
 */
export function MisTareasCliente({ tareas }: { tareas: TareaInstancia[] }) {
  const apertura = tareas.filter((t) => t.momento === "apertura");
  const cierre = tareas.filter((t) => t.momento === "cierre");

  if (tareas.length === 0) {
    return (
      <div className="flex max-w-2xl flex-col gap-2">
        <h1 className="font-heading text-xl text-dark">Mis tareas</h1>
        <p className="text-sm text-gray">No tienes tareas asignadas para hoy.</p>
      </div>
    );
  }

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <h1 className="font-heading text-xl text-dark">Mis tareas de hoy</h1>
      {apertura.length > 0 && (
        <GrupoMomento titulo="Apertura" tareas={apertura} />
      )}
      {cierre.length > 0 && <GrupoMomento titulo="Cierre" tareas={cierre} />}
    </div>
  );
}

function GrupoMomento({ titulo, tareas }: { titulo: string; tareas: TareaInstancia[] }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray">{titulo}</h2>
      {tareas
        .sort((a, b) => a.orden - b.orden)
        .map((tarea) => (
          <TarjetaTarea key={tarea.id} tarea={tarea} />
        ))}
    </section>
  );
}

function Checklist({
  items,
  bloqueada,
  ocupado,
  marcar,
}: {
  items: ChecklistItem[];
  bloqueada: boolean;
  ocupado: boolean;
  marcar: (indice: number, hecho: boolean) => void;
}) {
  return (
    <ul className="mt-3 flex flex-col gap-1.5">
      {items.map((item, indice) => (
        <li key={indice} className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={item.hecho}
            disabled={bloqueada || ocupado}
            onChange={(e) => marcar(indice, e.target.checked)}
          />
          <span className={item.hecho ? "text-gray line-through" : "text-dark"}>
            {item.texto}
          </span>
        </li>
      ))}
    </ul>
  );
}

function SeccionFoto({
  tarea,
  bloqueada,
  ocupado,
  subirFoto,
}: {
  tarea: TareaInstancia;
  bloqueada: boolean;
  ocupado: boolean;
  subirFoto: (formData: FormData) => void;
}) {
  if (!tarea.requiere_foto) return null;
  return (
    <div className="mt-3 flex flex-col gap-1.5">
      <span className="text-xs font-semibold text-gray">
        Foto de evidencia {tarea.tiene_foto ? "✓ subida" : "(obligatoria)"}
      </span>
      {!bloqueada && (
        <form action={subirFoto} className="flex items-center gap-2">
          <input
            type="file"
            name="archivo"
            accept="image/*"
            capture="environment"
            required
            disabled={ocupado}
            className="text-xs"
          />
          <button
            type="submit"
            disabled={ocupado}
            className="rounded-md bg-muted px-2 py-1 text-xs font-semibold text-dark disabled:opacity-50"
          >
            Subir
          </button>
        </form>
      )}
      {tarea.estado === "completada" && tarea.foto_valida === false && (
        <span className="text-xs font-semibold text-status-warning-texto">
          La foto no coincide con el momento en que se completó — revisar.
        </span>
      )}
    </div>
  );
}

function TarjetaTarea({ tarea }: { tarea: TareaInstancia }) {
  const router = useRouter();
  const [pendiente, iniciarTransicion] = useTransition();
  const [error, setError] = useState("");
  const [observacion, setObservacion] = useState(tarea.observacion ?? "");

  const bloqueada = tarea.estado !== "pendiente";

  function correr(promesa: () => Promise<{ error: string; ok: boolean }>) {
    setError("");
    iniciarTransicion(async () => {
      const r = await promesa();
      if (!r.ok) setError(r.error);
      else router.refresh();
    });
  }

  const marcar = (indice: number, hecho: boolean) =>
    correr(() => marcarItemAction(tarea.id, indice, hecho));
  const subirFoto = (formData: FormData) => correr(() => subirFotoAction(tarea.id, formData));
  const completar = () => correr(() => completarAction(tarea.id, observacion));

  const checklistCompleto = tarea.checklist.every((i) => i.hecho);
  const puedeCompletar =
    !bloqueada && checklistCompleto && (!tarea.requiere_foto || tarea.tiene_foto);

  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-[var(--sombra-1)]">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold text-dark">{tarea.nombre}</h3>
        <InsigniaEstado estado={tarea.estado} />
      </div>

      <Checklist
        items={tarea.checklist}
        bloqueada={bloqueada}
        ocupado={pendiente}
        marcar={marcar}
      />
      <SeccionFoto
        tarea={tarea}
        bloqueada={bloqueada}
        ocupado={pendiente}
        subirFoto={subirFoto}
      />

      {!bloqueada && (
        <div className="mt-3 flex flex-col gap-2">
          <input
            className="rounded-md border border-border px-2 py-1 text-sm"
            placeholder="Observación (opcional)"
            value={observacion}
            onChange={(e) => setObservacion(e.target.value)}
            maxLength={255}
          />
          <button
            type="button"
            onClick={completar}
            disabled={!puedeCompletar || pendiente}
            className="inline-flex w-fit items-center justify-center rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/85 disabled:pointer-events-none disabled:opacity-50"
          >
            {pendiente ? "Guardando..." : "Completar"}
          </button>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-2 text-sm font-semibold text-secondary">
          {error}
        </p>
      )}
    </div>
  );
}
