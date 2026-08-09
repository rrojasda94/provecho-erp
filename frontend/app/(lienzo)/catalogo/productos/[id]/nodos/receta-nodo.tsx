"use client";

import { useState } from "react";

import {
  catalogoApi,
  type Articulo,
  type RecetaDetalle,
} from "@/lib/catalogo";
import { ErrorApi } from "@/lib/cliente-api";
import { soles } from "@/lib/nodos";

/**
 * La receta que contiene un nodo, editable **desde el lienzo**.
 *
 * Esto revierte ADR-035 §4, que mandaba editar las cantidades solo en
 * Catálogo → Recetas. El motivo de aquella regla era la **duplicación**: el
 * mismo editor en dos pantallas hacía pensar que eran dos recetas distintas.
 * Acá no hay duplicación de concepto: el lienzo es el lugar de trabajo, y un
 * nodo del que no se puede abrir lo que contiene es un dibujo, no una
 * herramienta. El enlace a Catálogo → Recetas se conserva para lo que esta
 * vista no hace (crear, duplicar, escalar, renombrar).
 *
 * La cantidad acepta **aritmética** ("1000/3"): la evalúa el servidor y
 * devuelve el número ya redondeado a los decimales de la unidad del insumo
 * (RN-COM-024). El navegador nunca manda el resultado calculado por él.
 */
export function RecetaDelNodo({
  titulo,
  receta,
  articulos,
  onActualizada,
  onError,
}: {
  titulo: string;
  receta: RecetaDetalle | null;
  articulos: Articulo[];
  onActualizada: (r: RecetaDetalle) => void;
  onError: (mensaje: string) => void;
}) {
  const [nuevo, setNuevo] = useState("");
  const [cantidad, setCantidad] = useState("");
  const [guardando, setGuardando] = useState(false);

  if (!receta) {
    return (
      <p className="lienzo-nota">
        {titulo} no tiene receta todavía. Se le asigna una desde la ficha del
        producto.
      </p>
    );
  }

  const correr = async (accion: () => Promise<RecetaDetalle>) => {
    setGuardando(true);
    try {
      onActualizada(await accion());
    } catch (e) {
      onError(e instanceof ErrorApi ? e.message : "No se pudo guardar la receta.");
    } finally {
      setGuardando(false);
    }
  };

  const libres = articulos.filter(
    (a) => !receta.items.some((i) => i.articulo_id === a.id),
  );

  return (
    <div className={`lienzo-receta${guardando ? " ocupado" : ""}`}>
      <table className="lienzo-tabla">
        <tbody>
          {receta.items.length === 0 && (
            <tr>
              <td className="lienzo-nota">Receta vacía: agrega el primer insumo.</td>
            </tr>
          )}
          {receta.items.map((it) => (
            <tr key={it.id}>
              <td>
                {it.articulo_nombre}
                <span className="origen">
                  {it.unidad_medida_nombre}
                  {Number(it.merma_pct) > 0 ? ` · merma ${it.merma_pct}%` : ""}
                </span>
              </td>
              <td className="num">
                <input
                  className="lienzo-cantidad"
                  defaultValue={it.expresion ?? it.cantidad}
                  aria-label={`Cantidad de ${it.articulo_nombre}`}
                  title="Acepta operaciones: 1000/3, 250*1.5"
                  onBlur={(e) => {
                    const v = e.target.value.trim();
                    if (!v || v === (it.expresion ?? it.cantidad)) return;
                    // Se manda como `expresion` siempre: el servidor la
                    // evalúa y redondea a la UdM del insumo. Mandar el
                    // resultado calculado acá sería una segunda verdad.
                    correr(() =>
                      catalogoApi.editarItem(receta.id, it.id, { expresion: v }),
                    );
                  }}
                />
              </td>
              <td className="num">{soles(Number(it.costo_linea))}</td>
              <td className="num">
                <button
                  type="button"
                  className="nodo-accion riesgo"
                  aria-label={`Quitar ${it.articulo_nombre} de la receta`}
                  onClick={() =>
                    correr(() => catalogoApi.eliminarItem(receta.id, it.id))
                  }
                >
                  ×
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="lienzo-agregar-insumo">
        <select
          value={nuevo}
          aria-label="Insumo a agregar"
          onChange={(e) => setNuevo(e.target.value)}
        >
          <option value="">+ insumo…</option>
          {libres.map((a) => (
            <option key={a.id} value={a.id}>
              {a.nombre}
            </option>
          ))}
        </select>
        <input
          value={cantidad}
          onChange={(e) => setCantidad(e.target.value)}
          placeholder="cant."
          aria-label="Cantidad del insumo nuevo"
          title="Acepta operaciones: 1000/3"
        />
        <button
          type="button"
          className="lienzo-boton"
          disabled={!nuevo || !cantidad.trim() || guardando}
          onClick={() =>
            correr(async () => {
              const r = await catalogoApi.agregarItem(receta.id, {
                articulo_id: nuevo,
                expresion: cantidad.trim(),
              });
              setNuevo("");
              setCantidad("");
              return r;
            })
          }
        >
          Agregar
        </button>
      </div>

      <p className="lienzo-nota">
        Costo de la receta: <strong>{soles(Number(receta.costo_total))}</strong>{" "}
        · rinde {receta.rendimiento_cantidad}{" "}
        {receta.rendimiento_unidad_medida_nombre ?? ""}
      </p>
    </div>
  );
}
