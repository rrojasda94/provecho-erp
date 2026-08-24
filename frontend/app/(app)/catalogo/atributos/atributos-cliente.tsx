"use client";

import { useRef, useState } from "react";

import { catalogoApi, type Atributo, type ValorDeAtributo } from "@/lib/catalogo";
import { ErrorApi } from "@/lib/cliente-api";
import { aTitulo } from "@/lib/texto";

const MODOS: { valor: string; etiqueta: string; ayuda: string }[] = [
  {
    valor: "siempre",
    etiqueta: "Siempre",
    ayuda: "Genera una variante por cada combinación al vincularlo. Para lo que tiene receta y precio propios (Tamaño).",
  },
  {
    valor: "dinamica",
    etiqueta: "Dinámica",
    ayuda: "Genera la fila la primera vez que se vende esa combinación.",
  },
  {
    valor: "nunca",
    etiqueta: "Nunca",
    ayuda: "No genera ninguna fila: el valor viaja en la línea de venta y solo decide qué se descuenta (Mitad 1, sabores).",
  },
];

const DISPLAYS = [
  { valor: "radio", etiqueta: "Botones" },
  { valor: "pildoras", etiqueta: "Píldoras" },
  { valor: "select", etiqueta: "Desplegable" },
  { valor: "color", etiqueta: "Color" },
];

/**
 * Los atributos del catálogo, estilo Odoo 18: una pantalla propia y no una
 * herramienta de dibujo (ADR-063). Acá se declara el vocabulario —"Tamaño"
 * con Personal/Mediana/Familiar— que después cada producto ofrece con su
 * propio sobreprecio, desde su ficha.
 */
export function AtributosCliente({ inicial }: { inicial: Atributo[] }) {
  const [atributos, setAtributos] = useState(inicial);
  const [error, setError] = useState("");
  const [expandido, setExpandido] = useState<string | null>(null);

  function reemplazar(atributo: Atributo) {
    setAtributos((lista) =>
      lista.some((a) => a.id === atributo.id)
        ? lista.map((a) => (a.id === atributo.id ? atributo : a))
        : [...lista, atributo].sort((a, b) => a.orden - b.orden || a.nombre.localeCompare(b.nombre)),
    );
  }

  async function correr(accion: () => Promise<Atributo>) {
    setError("");
    try {
      reemplazar(await accion());
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo guardar el cambio.");
    }
  }

  async function borrar(atributo: Atributo) {
    if (!window.confirm(`¿Borrar el atributo "${atributo.nombre}"?`)) return;
    setError("");
    try {
      await catalogoApi.borrarAtributo(atributo.id);
      setAtributos((lista) => lista.filter((a) => a.id !== atributo.id));
    } catch (e) {
      // El 409 nombra los productos que lo ofrecen: es exactamente lo que
      // hace falta para desatascarse, así que se muestra tal cual.
      setError(e instanceof ErrorApi ? e.message : "No se pudo borrar el atributo.");
    }
  }

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-xl text-dark">Atributos</h1>
          <p className="text-xs text-gray">
            Tamaño, Mitad 1, sabores... cada producto elige, desde su ficha,
            cuáles ofrece y con qué sobreprecio.
          </p>
        </div>
        <NuevoAtributo onCreado={(a) => setAtributos((lista) => [...lista, a])} />
      </div>

      {error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {error}
        </p>
      )}

      {atributos.length === 0 ? (
        <p className="rounded-lg border border-dashed border-gray/30 p-6 text-center text-sm text-gray">
          Todavía no hay atributos. Crea el primero para empezar a armar
          tamaños, mitades o sabores.
        </p>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-gray">
            <tr>
              <th className="py-1 w-8" />
              <th className="py-1">Nombre</th>
              <th className="py-1 w-40">Modo de variante</th>
              <th className="py-1 w-36">Cómo se muestra</th>
              <th className="py-1 w-20">Orden</th>
              <th className="py-1 w-24">Valores</th>
              <th className="py-1 w-8" />
            </tr>
          </thead>
          <tbody>
            {atributos.map((atributo) => (
              <FilaAtributo
                key={atributo.id}
                atributo={atributo}
                expandido={expandido === atributo.id}
                onExpandir={() =>
                  setExpandido((id) => (id === atributo.id ? null : atributo.id))
                }
                onEditar={(cuerpo) =>
                  correr(() => catalogoApi.editarAtributo(atributo.id, cuerpo))
                }
                onBorrar={() => borrar(atributo)}
                onCambioDeValores={reemplazar}
                onError={setError}
              />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function FilaAtributo({
  atributo,
  expandido,
  onExpandir,
  onEditar,
  onBorrar,
  onCambioDeValores,
  onError,
}: {
  atributo: Atributo;
  expandido: boolean;
  onExpandir: () => void;
  onEditar: (cuerpo: Partial<{ nombre: string; modo_variante: string; display: string; orden: number }>) => void;
  onBorrar: () => void;
  onCambioDeValores: (atributo: Atributo) => void;
  onError: (mensaje: string) => void;
}) {
  const modo = MODOS.find((m) => m.valor === atributo.modo_variante);
  return (
    <>
      <tr className="border-t border-gray/20 align-top">
        <td className="py-2">
          <button
            type="button"
            onClick={onExpandir}
            className="text-gray hover:text-dark"
            aria-label={expandido ? "Ocultar valores" : "Ver valores"}
            aria-expanded={expandido}
          >
            {expandido ? "▾" : "▸"}
          </button>
        </td>
        <td className="py-2 pr-2">
          <input
            defaultValue={atributo.nombre}
            className="w-full font-semibold"
            aria-label={`Nombre de ${atributo.nombre}`}
            onBlur={(e) => {
              const nombre = aTitulo(e.target.value);
              e.target.value = nombre;
              if (nombre && nombre !== atributo.nombre) onEditar({ nombre });
            }}
          />
        </td>
        <td className="py-2 pr-2">
          <select
            defaultValue={atributo.modo_variante}
            className="w-full text-sm"
            title={modo?.ayuda}
            onChange={(e) => onEditar({ modo_variante: e.target.value })}
          >
            {MODOS.map((m) => (
              <option key={m.valor} value={m.valor} title={m.ayuda}>
                {m.etiqueta}
              </option>
            ))}
          </select>
        </td>
        <td className="py-2 pr-2">
          <select
            defaultValue={atributo.display}
            className="w-full text-sm"
            onChange={(e) => onEditar({ display: e.target.value })}
          >
            {DISPLAYS.map((d) => (
              <option key={d.valor} value={d.valor}>
                {d.etiqueta}
              </option>
            ))}
          </select>
        </td>
        <td className="py-2 pr-2">
          <input
            type="number"
            defaultValue={atributo.orden}
            className="w-16"
            aria-label={`Orden de ${atributo.nombre}`}
            onBlur={(e) => {
              const orden = Number(e.target.value);
              if (orden !== atributo.orden) onEditar({ orden });
            }}
          />
        </td>
        <td className="py-2 text-gray">{atributo.valores.length}</td>
        <td className="py-2 text-right">
          <button
            type="button"
            onClick={onBorrar}
            className="text-secondary hover:underline"
            aria-label={`Borrar ${atributo.nombre}`}
            title="Solo si ningún producto lo ofrece"
          >
            ×
          </button>
        </td>
      </tr>
      {expandido && (
        <tr className="border-t border-gray/10 bg-cream/40">
          <td />
          <td colSpan={6} className="py-3 pr-2">
            <ValoresDeAtributo
              atributo={atributo}
              onCambio={onCambioDeValores}
              onError={onError}
            />
          </td>
        </tr>
      )}
    </>
  );
}

function ValoresDeAtributo({
  atributo,
  onCambio,
  onError,
}: {
  atributo: Atributo;
  onCambio: (atributo: Atributo) => void;
  onError: (mensaje: string) => void;
}) {
  const [nuevo, setNuevo] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function editar(valor: ValorDeAtributo, cuerpo: Partial<{ nombre: string; orden: number; activo: boolean }>) {
    try {
      onCambio(await catalogoApi.editarValorDeAtributo(atributo.id, valor.id, cuerpo));
    } catch (e) {
      onError(e instanceof ErrorApi ? e.message : "No se pudo guardar el valor.");
    }
  }

  async function agregar() {
    if (!nuevo.trim()) return;
    setGuardando(true);
    try {
      onCambio(
        await catalogoApi.agregarValorDeAtributo(atributo.id, {
          nombre: nuevo,
          orden: atributo.valores.length,
        }),
      );
      setNuevo("");
    } catch (e) {
      onError(e instanceof ErrorApi ? e.message : "No se pudo agregar el valor.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {atributo.valores.length > 0 && (
        <table className="w-full max-w-lg text-sm">
          <thead className="text-left text-xs uppercase text-gray">
            <tr>
              <th className="py-1">Valor</th>
              <th className="py-1 w-16">Orden</th>
              <th className="py-1 w-20">Activo</th>
            </tr>
          </thead>
          <tbody>
            {atributo.valores.map((valor) => (
              <tr key={valor.id} className="border-t border-gray/10">
                <td className="py-1.5 pr-2">
                  <input
                    defaultValue={valor.nombre}
                    className="w-full"
                    aria-label={`Nombre de ${valor.nombre}`}
                    onBlur={(e) => {
                      const nombre = aTitulo(e.target.value);
                      e.target.value = nombre;
                      if (nombre && nombre !== valor.nombre) editar(valor, { nombre });
                    }}
                  />
                </td>
                <td className="py-1.5 pr-2">
                  <input
                    type="number"
                    defaultValue={valor.orden}
                    className="w-14"
                    aria-label={`Orden de ${valor.nombre}`}
                    onBlur={(e) => {
                      const orden = Number(e.target.value);
                      if (orden !== valor.orden) editar(valor, { orden });
                    }}
                  />
                </td>
                <td className="py-1.5">
                  <input
                    type="checkbox"
                    checked={valor.activo}
                    aria-label={`Activo: ${valor.nombre}`}
                    onChange={(e) => editar(valor, { activo: e.target.checked })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="flex items-end gap-2">
        <label className="flex flex-col gap-1 text-xs font-semibold">
          Nuevo valor
          <input
            value={nuevo}
            onChange={(e) => setNuevo(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && agregar()}
            placeholder="Familiar"
            className="w-40"
          />
        </label>
        <button
          type="button"
          onClick={agregar}
          disabled={guardando || !nuevo.trim()}
          className="rounded bg-primary px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50"
        >
          + Valor
        </button>
      </div>
    </div>
  );
}

function NuevoAtributo({ onCreado }: { onCreado: (atributo: Atributo) => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [nombre, setNombre] = useState("");
  const [modo, setModo] = useState("nunca");
  const [display, setDisplay] = useState("radio");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function crear() {
    setError("");
    setGuardando(true);
    try {
      const atributo = await catalogoApi.crearAtributo({
        nombre,
        modo_variante: modo,
        display,
      });
      onCreado(atributo);
      setNombre("");
      setModo("nunca");
      setDisplay("radio");
      dialogRef.current?.close();
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo crear el atributo.");
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
        + Nuevo atributo
      </button>
      <dialog ref={dialogRef} className="w-full max-w-md rounded-lg p-0 backdrop:bg-dark/40">
        <div className="flex flex-col gap-4 p-6">
          <h2 className="font-heading text-lg text-dark">Nuevo atributo</h2>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Nombre
            <input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              onBlur={() => setNombre((n) => aTitulo(n))}
              maxLength={80}
              placeholder="Tamaño"
            />
          </label>
          <fieldset className="flex flex-col gap-2 text-sm">
            <legend className="font-semibold">Modo de variante</legend>
            {MODOS.map((m) => (
              <label key={m.valor} className="flex items-start gap-2 font-normal">
                <input
                  type="radio"
                  name="modo"
                  className="mt-1"
                  checked={modo === m.valor}
                  onChange={() => setModo(m.valor)}
                />
                <span>
                  <span className="font-semibold">{m.etiqueta}</span>
                  <span className="block text-xs text-gray">{m.ayuda}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Cómo se muestra en el PDV
            <select value={display} onChange={(e) => setDisplay(e.target.value)}>
              {DISPLAYS.map((d) => (
                <option key={d.valor} value={d.valor}>
                  {d.etiqueta}
                </option>
              ))}
            </select>
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
