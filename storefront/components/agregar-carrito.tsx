"use client";

import { useMemo, useState } from "react";

import { vibrar } from "@/lib/haptica";
import { agregarAlCarrito } from "@/lib/carrito";
import {
  esDePago,
  extrasDePagoElegidos,
  extrasSueltos,
  gruposDe,
  MAXIMO_EXTRAS_DE_PAGO,
  precioUnitario,
  recargoDeValores,
  validar,
  valorEnConflicto,
  type AtributoOpcion,
  type ExtraOpcion,
  type Grupo,
  type Opciones,
  type Seleccion,
} from "@/lib/opciones";

/** Algo que se puede pedir: el producto o una de sus presentaciones, con lo que
 * admite (extras y sabores). */
export type Vendible = Opciones & {
  id: string;
  nombre: string;
  precio: string;
  disponible: boolean;
};

const PILDORA = "rounded-full border-2 border-negro px-3 py-1 text-xs font-bold disabled:opacity-40";
const ACTIVA = "bg-verde text-negro";

function Contador({
  valor,
  onCambio,
  maximo,
}: {
  valor: number;
  onCambio: (v: number) => void;
  maximo: number;
}) {
  return (
    <div className="flex items-center rounded border-2 border-negro">
      <button
        type="button"
        disabled={valor <= 0}
        onClick={() => onCambio(valor - 1)}
        className="px-2 font-bold disabled:opacity-30"
        aria-label="Menos"
      >
        −
      </button>
      <span className="w-6 text-center text-sm">{valor}</span>
      <button
        type="button"
        disabled={valor >= maximo}
        onClick={() => onCambio(valor + 1)}
        className="px-2 font-bold disabled:opacity-30"
        aria-label="Más"
      >
        +
      </button>
    </div>
  );
}

function ElegirValor({
  atributo,
  op,
  sel,
  onElegir,
}: {
  atributo: AtributoOpcion;
  op: Opciones;
  sel: Seleccion;
  onElegir: (valorId: string) => void;
}) {
  const elegido = sel.valores[atributo.id] ?? "";
  // 19 sabores en botones es una pantalla inusable: se pliegan en un desplegable.
  if (atributo.display === "select" || atributo.valores.length > 6) {
    return (
      <select
        value={elegido}
        onChange={(e) => onElegir(e.target.value)}
        className="rounded border-2 border-negro px-3 py-2 text-sm"
        aria-label={atributo.nombre}
      >
        <option value="">Elige…</option>
        {atributo.valores.map((v) => (
          <option key={v.id} value={v.id} disabled={valorEnConflicto(op, sel, v.id)}>
            {v.nombre}
            {Number(v.precio_extra) > 0 && ` (+ S/ ${v.precio_extra})`}
          </option>
        ))}
      </select>
    );
  }
  return (
    <div className="flex flex-wrap gap-2">
      {atributo.valores.map((v) => (
        <button
          key={v.id}
          type="button"
          disabled={valorEnConflicto(op, sel, v.id)}
          onClick={() => onElegir(v.id)}
          className={`${PILDORA} ${elegido === v.id ? ACTIVA : "bg-white"}`}
        >
          {v.nombre}
          {Number(v.precio_extra) > 0 && ` + S/ ${v.precio_extra}`}
        </button>
      ))}
    </div>
  );
}

function GrupoDeExtras({
  grupo,
  sel,
  onCambio,
}: {
  grupo: Grupo;
  sel: Seleccion;
  onCambio: (extras: Seleccion["extras"]) => void;
}) {
  const unaSola = grupo.maximo === 1;
  const cuantos = grupo.extras.filter((e) => (sel.extras[e.id] ?? 0) > 0).length;
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-bold uppercase text-negro">
        {grupo.nombre ?? "Opciones"}
        {grupo.minimo > 0 && <span className="ml-1 text-xs font-normal text-rojo">obligatorio</span>}
      </legend>
      <div className="flex flex-wrap gap-2">
        {grupo.extras.map((e) => {
          const activo = (sel.extras[e.id] ?? 0) > 0;
          return (
            <button
              key={e.id}
              type="button"
              disabled={!activo && !unaSola && grupo.maximo !== null && cuantos >= grupo.maximo}
              onClick={() => {
                const siguiente = { ...sel.extras };
                if (unaSola) {
                  for (const otro of grupo.extras) delete siguiente[otro.id];
                  // Con mínimo 0 se puede volver a "ninguno" tocando el mismo.
                  if (!activo || grupo.minimo > 0) siguiente[e.id] = 1;
                } else if (activo) {
                  delete siguiente[e.id];
                } else {
                  siguiente[e.id] = 1;
                }
                onCambio(siguiente);
              }}
              className={`${PILDORA} ${activo ? ACTIVA : "bg-white"}`}
            >
              {e.nombre}
              {Number(e.precio) > 0 && ` + S/ ${e.precio}`}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

function ExtrasDePago({
  extras,
  op,
  sel,
  onCambio,
}: {
  extras: ExtraOpcion[];
  op: Opciones;
  sel: Seleccion;
  onCambio: (extras: Seleccion["extras"]) => void;
}) {
  const usados = extrasDePagoElegidos(op, sel);
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-bold uppercase text-negro">
        Agrega extras{" "}
        <span className="text-xs font-normal text-humo">(máx. {MAXIMO_EXTRAS_DE_PAGO})</span>
      </legend>
      {extras.map((e) => {
        const valor = sel.extras[e.id] ?? 0;
        const tope = Math.min(
          e.maximo ?? MAXIMO_EXTRAS_DE_PAGO,
          valor + (esDePago(e) ? MAXIMO_EXTRAS_DE_PAGO - usados : MAXIMO_EXTRAS_DE_PAGO),
        );
        return (
          <div key={e.id} className="flex items-center justify-between text-sm">
            <span>
              {e.nombre} <span className="text-humo">+ S/ {e.precio}</span>
            </span>
            <Contador
              valor={valor}
              maximo={tope}
              onCambio={(v) => onCambio({ ...sel.extras, [e.id]: v })}
            />
          </div>
        );
      })}
    </fieldset>
  );
}

export function AgregarCarrito({
  fotoUrl,
  opciones,
}: {
  fotoUrl: string | null;
  opciones: Vendible[];
}) {
  const [seleccion, setSeleccion] = useState(opciones[0]?.id ?? "");
  const [sel, setSel] = useState<Seleccion>({ extras: {}, valores: {} });
  const [cantidad, setCantidad] = useState(1);
  const [agregado, setAgregado] = useState(false);

  const elegida = opciones.find((o) => o.id === seleccion) ?? opciones[0];
  const grupos = useMemo(() => (elegida ? gruposDe(elegida) : []), [elegida]);
  if (!elegida) return null;

  const suelto = extrasSueltos(elegida);
  const falta = validar(elegida, sel);
  const unitario = precioUnitario(Number(elegida.precio), elegida, sel);

  function cambiarPresentacion(id: string) {
    setSeleccion(id);
    // Cada tamaño ofrece lo suyo: lo elegido en otro ya no vale.
    setSel({ extras: {}, valores: {} });
  }

  function agregar() {
    if (!elegida || falta) return;
    const valores = elegida.atributos.flatMap((a) => {
      const v = a.valores.find((x) => x.id === sel.valores[a.id]);
      return v ? [{ id: v.id, nombre: v.nombre, atributo: a.nombre }] : [];
    });
    const extras = elegida.extras.flatMap((e) =>
      (sel.extras[e.id] ?? 0) > 0
        ? [{ id: e.id, nombre: e.nombre, precio: e.precio, cantidad: sel.extras[e.id] }]
        : [],
    );
    agregarAlCarrito(
      {
        productoComercialId: elegida.id,
        nombre: elegida.nombre,
        // Precio de una unidad con el recargo de los sabores, sin los extras
        // (cada extra viaja con su propio precio).
        precio: (Number(elegida.precio) + recargoDeValores(elegida, sel)).toFixed(2),
        fotoUrl,
        extras,
        valores,
      },
      cantidad,
    );
    vibrar(15);
    setAgregado(true);
    setTimeout(() => setAgregado(false), 1500);
  }

  return (
    <div className="flex flex-col gap-4 border-t-2 border-negro/10 pt-4">
      {opciones.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {opciones.map((o) => (
            <button
              key={o.id}
              type="button"
              disabled={!o.disponible}
              onClick={() => cambiarPresentacion(o.id)}
              className={`${PILDORA} uppercase ${seleccion === o.id ? ACTIVA : "bg-white"}`}
            >
              {o.nombre}
            </button>
          ))}
        </div>
      )}

      {elegida.atributos.map((a) => (
        <fieldset key={a.id} className="flex flex-col gap-2">
          <legend className="text-sm font-bold uppercase text-negro">{a.nombre}</legend>
          <ElegirValor
            atributo={a}
            op={elegida}
            sel={sel}
            onElegir={(valorId) =>
              setSel((s) => ({ ...s, valores: { ...s.valores, [a.id]: valorId } }))
            }
          />
        </fieldset>
      ))}

      {grupos.map((g) => (
        <GrupoDeExtras
          key={g.id}
          grupo={g}
          sel={sel}
          onCambio={(extras) => setSel((s) => ({ ...s, extras }))}
        />
      ))}

      {suelto.length > 0 && (
        <ExtrasDePago
          extras={suelto}
          op={elegida}
          sel={sel}
          onCambio={(extras) => setSel((s) => ({ ...s, extras }))}
        />
      )}

      {falta && <p className="text-xs text-rojo">{falta}</p>}

      <div className="flex items-center gap-3">
        <div className="flex items-center rounded border-2 border-negro">
          <button
            type="button"
            onClick={() => setCantidad((c) => Math.max(1, c - 1))}
            className="px-3 py-1 font-bold transition-transform active:scale-90"
            aria-label="Menos"
          >
            −
          </button>
          <span className="w-8 text-center">{cantidad}</span>
          <button
            type="button"
            onClick={() => setCantidad((c) => Math.min(20, c + 1))}
            className="px-3 py-1 font-bold transition-transform active:scale-90"
            aria-label="Más"
          >
            +
          </button>
        </div>
        <button
          type="button"
          disabled={!elegida.disponible || falta !== null}
          onClick={agregar}
          className={`sombra-dura flex-1 rounded px-4 py-2 font-bold uppercase text-negro transition-colors hover:bg-verde-hover disabled:opacity-50 ${
            agregado ? "bg-oliva" : "bg-verde"
          }`}
        >
          {agregado ? "¡Agregado! ✓" : `Agregar — S/ ${(unitario * cantidad).toFixed(2)}`}
        </button>
      </div>
    </div>
  );
}
