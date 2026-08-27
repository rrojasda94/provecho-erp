"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useMemo, useState, useTransition } from "react";

import {
  BOTON_FILA,
  DialogoFormulario,
  valor,
} from "@/components/formulario/dialogo-formulario";

import {
  crearMesaAction,
  eliminarMesaAction,
  guardarMesaAction,
  moverMesaAction,
} from "../actions";

export type Sucursal = { id: string; nombre: string };
export type Mesa = {
  id: string;
  sucursal_id: string;
  numero: number;
  zona: string | null;
  capacidad: number | null;
  pos_x: number;
  pos_y: number;
  activa: boolean;
};

// Espejo de `rules.MESA_COLUMNAS` (backend): el plano tiene 12 columnas. Si
// esa constante cambia, esta se actualiza con ella — no hay endpoint que la
// exponga, y traerla solo para esto sería una vuelta de más.
const COLUMNAS = 12;

function DialogoNuevaMesa({ sucursalId }: { sucursalId: string }) {
  return (
    <DialogoFormulario
      titulo="Nueva mesa"
      disparador="+ Nueva mesa"
      etiquetaEnvio="Crear"
      etiquetaPendiente="Creando..."
      accion={crearMesaAction}
      ayuda="El número lo asigna el sistema: el salón se numera 1, 2, 3... sin huecos."
    >
      <input type="hidden" name="sucursal_id" value={sucursalId} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Zona
        <input name="zona" maxLength={50} placeholder="Salón, Terraza, Barra..." />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Capacidad
        <input name="capacidad" type="number" min={1} placeholder="4" />
      </label>
    </DialogoFormulario>
  );
}

function DialogoEditarMesa({
  mesa,
  esLaUltima,
  onEliminar,
}: {
  mesa: Mesa;
  esLaUltima: boolean;
  onEliminar: () => void;
}) {
  return (
    <DialogoFormulario
      titulo={`Mesa ${mesa.numero}`}
      disparador={
        <span className="flex h-full w-full flex-col items-start gap-0.5 text-left">
          <span className="text-lg font-bold text-dark">{mesa.numero}</span>
          <span className="text-xs text-gray">
            {mesa.zona ?? "Sin zona"}
            {mesa.capacidad ? ` · ${mesa.capacidad}p` : ""}
          </span>
        </span>
      }
      claseDisparador="flex h-full w-full items-start rounded-xl border border-border bg-card p-2.5 transition-colors hover:bg-muted"
      accion={guardarMesaAction}
      ayuda={
        esLaUltima
          ? "Es la de número más alto: se puede quitar."
          : "El salón se numera 1..n sin huecos: solo se quita la última mesa."
      }
    >
      <input type="hidden" name="id" value={mesa.id} />
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Zona
        <input
          name="zona"
          maxLength={50}
          defaultValue={valor(mesa.zona)}
          placeholder="Salón, Terraza, Barra..."
        />
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Capacidad
        <input
          name="capacidad"
          type="number"
          min={1}
          defaultValue={valor(mesa.capacidad)}
        />
      </label>
      {esLaUltima && (
        <button
          type="button"
          className={`${BOTON_FILA} self-start text-secondary`}
          onClick={onEliminar}
        >
          Quitar mesa {mesa.numero}
        </button>
      )}
    </DialogoFormulario>
  );
}

/** Celda vacía del plano: solo existe como blanco donde soltar una mesa
 * arrastrada — no dibuja nada mientras nadie arrastra sobre ella. */
function CeldaVacia({
  x,
  y,
  onSoltar,
}: {
  x: number;
  y: number;
  onSoltar: (mesaId: string, x: number, y: number) => void;
}) {
  const [sobre, setSobre] = useState(false);
  return (
    <div
      style={{ gridColumn: x + 1, gridRow: y + 1 }}
      onDragOver={(e) => {
        e.preventDefault();
        setSobre(true);
      }}
      onDragLeave={() => setSobre(false)}
      onDrop={(e) => {
        e.preventDefault();
        setSobre(false);
        const mesaId = e.dataTransfer.getData("text/plain");
        if (mesaId) onSoltar(mesaId, x, y);
      }}
      className={`rounded-xl border border-dashed ${
        sobre ? "border-primary bg-primary/10" : "border-border/40"
      }`}
    />
  );
}

export function MesasCliente({
  mesas,
  sucursales,
  sucursalId,
  puedeGestionar,
}: {
  mesas: Mesa[];
  sucursales: Sucursal[];
  sucursalId: string;
  puedeGestionar: boolean;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [, startTransition] = useTransition();

  const numeroMaximo = mesas.reduce((max, m) => Math.max(max, m.numero), 0);
  const filas = mesas.reduce((max, m) => Math.max(max, m.pos_y), -1) + 2;
  const porCelda = useMemo(() => {
    const mapa = new Map<string, Mesa>();
    for (const m of mesas) mapa.set(`${m.pos_x},${m.pos_y}`, m);
    return mapa;
  }, [mesas]);

  function mover(mesaId: string, x: number, y: number) {
    setError("");
    startTransition(async () => {
      const r = await moverMesaAction(mesaId, x, y);
      if (!r.ok) setError(r.error);
    });
  }

  function eliminar(mesa: Mesa) {
    if (!window.confirm(`¿Quitar la mesa ${mesa.numero}? Es la de número más alto.`)) {
      return;
    }
    setError("");
    startTransition(async () => {
      const r = await eliminarMesaAction(mesa.id);
      if (!r.ok) setError(r.error);
    });
  }

  const celdas: ReactNode[] = [];
  for (let y = 0; y < filas; y++) {
    for (let x = 0; x < COLUMNAS; x++) {
      const mesa = porCelda.get(`${x},${y}`);
      if (mesa) {
        celdas.push(
          <div
            key={mesa.id}
            draggable={puedeGestionar}
            onDragStart={(e) => e.dataTransfer.setData("text/plain", mesa.id)}
            style={{ gridColumn: x + 1, gridRow: y + 1 }}
          >
            <DialogoEditarMesa
              mesa={mesa}
              esLaUltima={mesa.numero === numeroMaximo}
              onEliminar={() => eliminar(mesa)}
            />
          </div>,
        );
      } else if (puedeGestionar) {
        celdas.push(<CeldaVacia key={`${x}-${y}`} x={x} y={y} onSoltar={mover} />);
      }
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="font-heading text-xl italic uppercase text-dark">Mesas</h1>
        {puedeGestionar && <DialogoNuevaMesa sucursalId={sucursalId} />}
      </div>
      <label className="flex max-w-xs flex-col gap-1 text-sm font-semibold">
        Sucursal
        <select
          value={sucursalId}
          onChange={(e) => router.push(`/ventas/mesas?sucursal=${e.target.value}`)}
        >
          {sucursales.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nombre}
            </option>
          ))}
        </select>
      </label>
      <p className="text-sm text-gray">
        El número lo asigna el sistema y no se edita: el salón se numera 1..n sin
        huecos. Arrastra una mesa para ubicarla en el plano.
      </p>
      {error && (
        <p role="status" className="text-sm text-secondary">
          {error}
        </p>
      )}
      {mesas.length === 0 ? (
        <p className="text-gray">Esta sucursal no tiene mesas todavía.</p>
      ) : (
        <div
          className="grid gap-2"
          style={{
            gridTemplateColumns: `repeat(${COLUMNAS}, minmax(4.5rem, 1fr))`,
            gridAutoRows: "5.5rem",
          }}
        >
          {celdas}
        </div>
      )}
    </div>
  );
}
