"use client";

import type { Articulo } from "@/lib/catalogo";
import { cantidadCorta, fusionar, margen, soles } from "@/lib/nodos";

/**
 * Lo que resulta del camino elegido: qué lleva el plato, qué cuesta y qué
 * deja. Es el nodo `Plato` desplegado.
 *
 * Panel acoplado y no flotante de vidrio: es una tabla densa de números
 * pequeños, que es justo donde el vidrio estorba, y tapando nodos se pierde
 * la mitad de la pantalla que se está mirando. Se pliega a un riel con el
 * total para que el lienzo pueda ir ancho.
 *
 * Los números salen de `lib/nodos.ts` sin tocarlos: esto solo los pinta.
 */

export const MODALIDADES = ["mesa", "takeout", "delivery"];

function Cifra({
  termino,
  valor,
  fuerte,
}: {
  termino: string;
  valor: string;
  fuerte?: boolean;
}) {
  return (
    <div className={`lienzo-cifra${fuerte ? " fuerte" : ""}`}>
      <dt>{termino}</dt>
      <dd>{valor}</dd>
    </div>
  );
}

/** Plegado: el lienzo se lleva el ancho y queda el número que importa. */
function Riel({
  costo,
  pct,
  onDesplegar,
}: {
  costo: number;
  pct: number | null;
  onDesplegar: () => void;
}) {
  return (
    <aside className="lienzo-inspector plegado">
      <button
        type="button"
        className="lienzo-plegar"
        onClick={onDesplegar}
        aria-label="Mostrar el detalle del plato"
      >
        ‹
      </button>
      <span className="lienzo-riel">
        {soles(costo)}
        {pct === null ? "" : ` · ${pct.toFixed(0)} %`}
      </span>
    </aside>
  );
}

export function Inspector({
  titulo,
  fusion,
  empaque,
  empaqueAplica,
  costoTotal,
  modalidad,
  onModalidad,
  precio,
  onPrecio,
  faltantes,
  plegado,
  onPlegar,
  editor,
  nodoTitulo,
  verEditor,
  onVerEditor,
}: {
  titulo: string;
  fusion: ReturnType<typeof fusionar>;
  empaque: Articulo | null;
  empaqueAplica: boolean;
  costoTotal: number;
  modalidad: string;
  onModalidad: (m: string) => void;
  precio: string;
  onPrecio: (p: string) => void;
  faltantes: string[];
  plegado: boolean;
  onPlegar: () => void;
  /** La receta del nodo seleccionado, si hay uno. */
  editor?: React.ReactNode;
  nodoTitulo?: string | null;
  verEditor: boolean;
  onVerEditor: (v: boolean) => void;
}) {
  const valorPrecio = Number(precio) || 0;
  const { monto, pct } = margen(valorPrecio, costoTotal);

  if (plegado) {
    return <Riel costo={costoTotal} pct={pct} onDesplegar={onPlegar} />;
  }

  return (
    <aside className="lienzo-inspector">
      <div className="lienzo-campo">
        <h2>Plato armado</h2>
        <button
          type="button"
          className="lienzo-plegar"
          onClick={onPlegar}
          aria-label="Plegar el detalle del plato"
        >
          ›
        </button>
      </div>
      {editor && nodoTitulo ? (
        <Pestanas
          nodoTitulo={nodoTitulo}
          verEditor={verEditor}
          onVerEditor={onVerEditor}
        />
      ) : null}

      {editor && verEditor ? (
        editor
      ) : (
        <DetalleDelPlato
          titulo={titulo}
          fusion={fusion}
          empaque={empaque}
          empaqueAplica={empaqueAplica}
          costoTotal={costoTotal}
          modalidad={modalidad}
          onModalidad={onModalidad}
          precio={precio}
          onPrecio={onPrecio}
          faltantes={faltantes}
          monto={monto}
          pct={pct}
        />
      )}
    </aside>
  );
}

/** Dos vistas del mismo panel: el plato que se está armando, o la receta del
 * nodo que se tocó. Se separa en su propio componente para que el inspector
 * no cruce el límite de complejidad del repo. */
function Pestanas({
  nodoTitulo,
  verEditor,
  onVerEditor,
}: {
  nodoTitulo: string;
  verEditor: boolean;
  onVerEditor: (v: boolean) => void;
}) {
  return (
    <div className="lienzo-pestanas" role="tablist">
      <button
        type="button"
        role="tab"
        aria-selected={!verEditor}
        className={!verEditor ? "sel" : ""}
        onClick={() => onVerEditor(false)}
      >
        Plato
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={verEditor}
        className={verEditor ? "sel" : ""}
        onClick={() => onVerEditor(true)}
      >
        {nodoTitulo}
      </button>
    </div>
  );
}


/** El plato que se está armando: qué lleva, qué cuesta y qué deja. Vive
 * aparte del inspector para que este quede en lo suyo —elegir qué se mira— y
 * no cruce el límite de complejidad del repo. */
function DetalleDelPlato({
  titulo,
  fusion,
  empaque,
  empaqueAplica,
  costoTotal,
  modalidad,
  onModalidad,
  precio,
  onPrecio,
  faltantes,
  monto,
  pct,
}: {
  titulo: string;
  fusion: ReturnType<typeof fusionar>;
  empaque: Articulo | null;
  empaqueAplica: boolean;
  costoTotal: number;
  modalidad: string;
  onModalidad: (m: string) => void;
  precio: string;
  onPrecio: (p: string) => void;
  faltantes: string[];
  monto: number;
  pct: number | null;
}) {
  const valorPrecio = Number(precio) || 0;
  return (
    <>
      <p className="lienzo-nota">{titulo}</p>

      {faltantes.length > 0 && (
        <p className="lienzo-falta">
          Falta elegir: {faltantes.join(", ")}. El PDV no dejaría agregarlo al
          carrito así.
        </p>
      )}

      <table className="lienzo-tabla">
        <tbody>
          {fusion.lineas.length === 0 && (
            <tr>
              <td className="lienzo-nota">
                Nada todavía: elige un tamaño con receta.
              </td>
            </tr>
          )}
          {fusion.lineas.map((l) => (
            <tr key={l.articuloId} className={l.quitado ? "fuera" : ""}>
              <td>
                {l.articulo}
                <span className="origen">{l.origen}</span>
              </td>
              <td className="num">
                {cantidadCorta(l.cantidad)} {l.unidad}
              </td>
              <td className="num">{soles(l.costo)}</td>
            </tr>
          ))}
          {empaque && (
            <tr className={empaqueAplica ? "" : "fuera"}>
              <td>
                {empaque.nombre}
                <span className="origen">Empaque</span>
              </td>
              <td className="num">1</td>
              <td className="num">{soles(Number(empaque.costo_promedio))}</td>
            </tr>
          )}
        </tbody>
      </table>

      <label className="lienzo-campo">
        Modalidad
        <select value={modalidad} onChange={(e) => onModalidad(e.target.value)}>
          {MODALIDADES.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </label>

      <dl className="lienzo-cifras">
        <Cifra termino="Costo del plato" valor={soles(costoTotal)} fuerte />
        {fusion.costoQuitado > 0 && (
          <Cifra
            termino="No se descuenta (restas)"
            valor={soles(fusion.costoQuitado)}
          />
        )}
      </dl>

      <label className="lienzo-campo">
        Precio de venta
        <input
          value={precio}
          onChange={(e) => onPrecio(e.target.value)}
          inputMode="decimal"
          placeholder="S/"
        />
      </label>
      <p className="lienzo-nota">
        Se teclea acá: el precio que cobra el PDV sale de la lista vigente de
        la sucursal (RN-PRC-003), no de esta pantalla.
      </p>

      {valorPrecio > 0 && (
        <dl className="lienzo-cifras">
          <Cifra termino="Margen" valor={soles(monto)} fuerte />
          <Cifra
            termino="Margen %"
            valor={pct === null ? "—" : `${pct.toFixed(1)} %`}
          />
        </dl>
      )}
    </>
  );
}
