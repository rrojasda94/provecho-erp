"use client";

import { useCallback, useEffect, useState } from "react";

import { evaluar, formatear } from "@/lib/aritmetica";
import {
  catalogoApi,
  type Articulo,
  type RecetaDetalle,
  type RecetaItem,
  type UnidadMedida,
} from "@/lib/catalogo";
import { ErrorApi } from "@/lib/cliente-api";
import { aTitulo } from "@/lib/texto";

/**
 * Receta editada dentro de la ficha del producto (patrón Odoo): no se sale
 * a otra pantalla para decir de qué está hecha una pizza.
 *
 * Cada acción devuelve la receta completa desde el servidor y con eso se
 * repinta. Es a propósito: el redondeo por unidad de medida lo decide el
 * backend, y si la pantalla mantuviera su propio número, mostraría uno y se
 * descontaría otro.
 */
export function RecetaEditor({
  recetaId,
  nombreSugerido,
  articulos,
  unidades,
  onRecetaCreada,
}: {
  recetaId: string | null;
  nombreSugerido: string;
  articulos: Articulo[];
  unidades: UnidadMedida[];
  onRecetaCreada: (id: string) => void;
}) {
  const [receta, setReceta] = useState<RecetaDetalle | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  // Empezar una receta desde cero para un producto que ya tiene otra: sin
  // esto, la única salida era duplicar la existente.
  const [creandoOtra, setCreandoOtra] = useState(false);

  useEffect(() => {
    if (!recetaId) {
      setReceta(null);
      return;
    }
    setCreandoOtra(false);
    catalogoApi.receta(recetaId).then(setReceta).catch(() => setReceta(null));
  }, [recetaId]);

  const correr = useCallback(async (accion: () => Promise<RecetaDetalle>) => {
    setError("");
    setOcupado(true);
    try {
      setReceta(await accion());
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo guardar el cambio.");
    } finally {
      setOcupado(false);
    }
  }, []);

  if (!recetaId || creandoOtra) {
    return (
      <NuevaReceta
        nombreSugerido={nombreSugerido}
        unidades={unidades}
        onCreada={onRecetaCreada}
        onCancelar={creandoOtra ? () => setCreandoOtra(false) : undefined}
      />
    );
  }
  if (!receta) return <p className="text-sm text-gray">Cargando receta...</p>;

  const udmDe = (item: RecetaItem) => item.decimales;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <Encabezado
          receta={receta}
          unidades={unidades}
          deshabilitado={ocupado}
          onEditar={(cuerpo) =>
            correr(() => catalogoApi.editarReceta(receta.id, cuerpo))
          }
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={ocupado}
            onClick={() => setCreandoOtra(true)}
            className="rounded border border-gray px-3 py-1.5 text-xs font-semibold text-dark disabled:opacity-50"
            title="Arma otra receta desde cero para este producto. La actual queda como está"
          >
            Otra receta
          </button>
          <Escalar
            deshabilitado={ocupado}
            onEscalar={(factor) =>
              correr(() => catalogoApi.escalarReceta(receta.id, factor))
            }
          />
          <button
            type="button"
            disabled={ocupado}
            onClick={async () => {
              const copia = await catalogoApi.duplicarReceta(receta.id);
              onRecetaCreada(copia.id);
            }}
            className="rounded border border-gray px-3 py-1.5 text-xs font-semibold text-dark disabled:opacity-50"
            title="Crea una copia con el sufijo (copy) y este producto pasa a usarla. La receta original queda intacta para quien la comparta"
          >
            Duplicar
          </button>
        </div>
      </div>

      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-gray">
          <tr>
            <th className="py-1">Insumo</th>
            <th className="py-1 w-40">Cantidad</th>
            <th className="py-1 w-24">Unidad</th>
            <th className="py-1 w-24">Merma %</th>
            <th className="py-1 w-24 text-right">Costo</th>
            <th className="py-1 w-8" />
          </tr>
        </thead>
        <tbody>
          {receta.items.map((item) => (
            <tr key={item.id} className="border-t border-gray/20">
              <td className="py-1.5">{item.articulo_nombre}</td>
              <td className="py-1.5">
                <CampoCantidad
                  valor={item.expresion ?? item.cantidad}
                  decimales={udmDe(item)}
                  deshabilitado={ocupado}
                  onGuardar={(cuerpo) =>
                    correr(() => catalogoApi.editarItem(receta.id, item.id, cuerpo))
                  }
                />
              </td>
              <td className="py-1.5 text-gray">{item.unidad_medida_nombre}</td>
              <td className="py-1.5">
                <input
                  type="number"
                  min={0}
                  max={99}
                  step="0.01"
                  defaultValue={item.merma_pct}
                  disabled={ocupado}
                  className="w-20"
                  onBlur={(e) => {
                    if (e.target.value === item.merma_pct) return;
                    correr(() =>
                      catalogoApi.editarItem(receta.id, item.id, {
                        merma_pct: e.target.value,
                      }),
                    );
                  }}
                />
              </td>
              <td className="py-1.5 text-right">
                S/ {Number(item.costo_linea).toFixed(2)}
              </td>
              <td className="py-1.5 text-right">
                <button
                  type="button"
                  disabled={ocupado}
                  onClick={() =>
                    correr(() => catalogoApi.eliminarItem(receta.id, item.id))
                  }
                  className="text-secondary hover:underline"
                  aria-label={`Quitar ${item.articulo_nombre}`}
                >
                  ×
                </button>
              </td>
            </tr>
          ))}
          {receta.items.length === 0 && (
            <tr>
              <td colSpan={6} className="py-3 text-gray">
                Todavía no tiene insumos.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <NuevaLinea
        articulos={articulos}
        unidades={unidades}
        yaUsados={receta.items.map((i) => i.articulo_id)}
        deshabilitado={ocupado}
        onAgregar={(cuerpo) => correr(() => catalogoApi.agregarItem(receta.id, cuerpo))}
      />

      {error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {error}
        </p>
      )}
    </div>
  );
}

/**
 * Nombre, rendimiento y unidad de la receta, editables donde se leen.
 *
 * Sin esto, duplicar no servía para nada: la copia nacía con "(copy)" en el
 * nombre y no había forma de llamarla "Pizza Peperoni Familiar". Cada campo
 * guarda al salir, no hay botón "Guardar" — es la misma regla que en el
 * resto de la ficha.
 */
function Encabezado({
  receta,
  unidades,
  deshabilitado,
  onEditar,
}: {
  receta: RecetaDetalle;
  unidades: UnidadMedida[];
  deshabilitado: boolean;
  onEditar: (cuerpo: {
    nombre?: string;
    rendimiento_cantidad?: string;
    rendimiento_unidad_medida_id?: string;
  }) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <input
        key={`${receta.id}-nombre`}
        defaultValue={receta.nombre}
        disabled={deshabilitado}
        maxLength={150}
        aria-label="Nombre de la receta"
        className="min-w-64 font-semibold text-dark"
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
        }}
        onBlur={(e) => {
          const nombre = aTitulo(e.target.value);
          e.target.value = nombre;
          if (nombre && nombre !== receta.nombre) onEditar({ nombre });
        }}
      />
      <div className="flex flex-wrap items-center gap-2 text-xs text-gray">
        <span>Rinde</span>
        <input
          key={`${receta.id}-rinde`}
          defaultValue={receta.rendimiento_cantidad}
          disabled={deshabilitado}
          className="w-20"
          aria-label="Rendimiento"
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
          onBlur={(e) => {
            const valor = e.target.value.trim();
            if (valor && Number(valor) > 0 && valor !== receta.rendimiento_cantidad) {
              onEditar({ rendimiento_cantidad: valor });
            }
          }}
        />
        <select
          value={receta.rendimiento_unidad_medida_id}
          disabled={deshabilitado}
          aria-label="Unidad del rendimiento"
          onChange={(e) => onEditar({ rendimiento_unidad_medida_id: e.target.value })}
        >
          {unidades.map((u) => (
            <option key={u.id} value={u.id}>
              {u.nombre}
            </option>
          ))}
        </select>
        <span>· costo S/ {Number(receta.costo_total).toFixed(2)}</span>
      </div>
    </div>
  );
}

/**
 * Campo de cantidad que acepta aritmética: "1000/3", "250*1.5".
 *
 * Lo tecleado se manda como `expresion` y el servidor devuelve el número
 * ya redondeado a los decimales de la unidad del insumo. La vista previa
 * de acá abajo es solo para que el usuario vea el resultado antes de
 * soltar el campo.
 */
function CampoCantidad({
  valor,
  decimales,
  deshabilitado,
  onGuardar,
}: {
  valor: string;
  decimales: number;
  deshabilitado: boolean;
  onGuardar: (cuerpo: { cantidad?: string; expresion?: string }) => void;
}) {
  const [texto, setTexto] = useState(valor);
  useEffect(() => setTexto(valor), [valor]);

  const esOperacion = /[+\-*/()]/.test(texto.trim().replace(/^-/, ""));
  const previa = esOperacion ? evaluar(texto) : null;

  return (
    <div className="flex flex-col">
      <input
        value={texto}
        disabled={deshabilitado}
        inputMode="text"
        className="w-32"
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
        }}
        onBlur={() => {
          if (texto.trim() === valor.trim()) return;
          onGuardar(
            esOperacion ? { expresion: texto.trim() } : { cantidad: texto.trim() },
          );
        }}
      />
      {previa !== null && (
        <span className="text-xs text-gray">= {formatear(previa, decimales)}</span>
      )}
    </div>
  );
}

function NuevaLinea({
  articulos,
  unidades,
  yaUsados,
  deshabilitado,
  onAgregar,
}: {
  articulos: Articulo[];
  unidades: UnidadMedida[];
  yaUsados: string[];
  deshabilitado: boolean;
  onAgregar: (cuerpo: {
    articulo_id: string;
    cantidad?: string;
    expresion?: string;
    merma_pct?: string;
  }) => void;
}) {
  const disponibles = articulos.filter(
    (a) => !a.archivado && !yaUsados.includes(a.id),
  );
  const [articuloId, setArticuloId] = useState("");
  const [texto, setTexto] = useState("");

  const articulo = disponibles.find((a) => a.id === articuloId);
  // La unidad la pone el insumo: la receta no la elige (RN-UDM-001).
  const udm = unidades.find((u) => u.id === articulo?.unidad_medida_id);
  const esOperacion = /[+\-*/()]/.test(texto);
  const previa = esOperacion ? evaluar(texto) : null;

  function agregar() {
    if (!articuloId || !texto.trim()) return;
    onAgregar({
      articulo_id: articuloId,
      ...(esOperacion ? { expresion: texto.trim() } : { cantidad: texto.trim() }),
    });
    setArticuloId("");
    setTexto("");
  }

  return (
    <div className="flex flex-wrap items-end gap-2 rounded bg-cream/60 p-3">
      <label className="flex flex-col gap-1 text-xs font-semibold">
        Insumo
        <select
          value={articuloId}
          onChange={(e) => setArticuloId(e.target.value)}
          className="min-w-56"
        >
          <option value="">Elegir insumo...</option>
          {disponibles.map((a) => (
            <option key={a.id} value={a.id}>
              {a.nombre}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs font-semibold">
        Cantidad {udm ? `(${udm.nombre})` : ""}
        <input
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") agregar();
          }}
          placeholder="180 o 1000/3"
          className="w-36"
        />
      </label>
      {previa !== null && udm && (
        <span className="pb-2 text-xs text-gray">
          = {formatear(previa, udm.decimales)} {udm.nombre}
        </span>
      )}
      <button
        type="button"
        onClick={agregar}
        disabled={deshabilitado || !articuloId || !texto.trim()}
        className="rounded bg-primary px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50"
      >
        Agregar insumo
      </button>
    </div>
  );
}

function Escalar({
  deshabilitado,
  onEscalar,
}: {
  deshabilitado: boolean;
  onEscalar: (factor: string) => void;
}) {
  const [factor, setFactor] = useState("");
  return (
    <div className="flex items-end gap-1">
      <input
        value={factor}
        onChange={(e) => setFactor(e.target.value)}
        placeholder="x1.5"
        className="w-16"
        aria-label="Factor de escala"
      />
      <button
        type="button"
        disabled={deshabilitado || !Number(factor)}
        onClick={() => {
          onEscalar(factor);
          setFactor("");
        }}
        className="rounded border border-gray px-3 py-1.5 text-xs font-semibold text-dark disabled:opacity-50"
        title="Multiplica todas las cantidades, redondeando cada una con los decimales de su unidad"
      >
        Escalar
      </button>
    </div>
  );
}

function NuevaReceta({
  nombreSugerido,
  unidades,
  onCreada,
  onCancelar,
}: {
  nombreSugerido: string;
  unidades: UnidadMedida[];
  onCreada: (id: string) => void;
  /** Solo cuando se llegó acá desde "Otra receta": hay a dónde volver. */
  onCancelar?: () => void;
}) {
  const [nombre, setNombre] = useState(nombreSugerido);
  const [cantidad, setCantidad] = useState("1");
  const [udmId, setUdmId] = useState(unidades[0]?.id ?? "");
  const [error, setError] = useState("");
  const [recetas, setRecetas] = useState<{ id: string; nombre: string }[]>([]);

  useEffect(() => {
    catalogoApi.recetas().then(setRecetas).catch(() => setRecetas([]));
  }, []);

  async function crear() {
    setError("");
    try {
      const receta = await catalogoApi.crearReceta({
        nombre,
        rendimiento_cantidad: cantidad,
        rendimiento_unidad_medida_id: udmId,
      });
      onCreada(receta.id);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo crear la receta.");
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded bg-cream/60 p-3">
      <p className="text-sm text-gray">
        {onCancelar
          ? "Nueva receta para este producto. La que usa ahora queda intacta."
          : "Este producto todavía no tiene receta. Créala o reusa una existente."}
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs font-semibold">
          Nombre de la receta
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            onBlur={() => setNombre((n) => aTitulo(n))}
            className="min-w-56"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-semibold">
          Rinde
          <input
            value={cantidad}
            onChange={(e) => setCantidad(e.target.value)}
            className="w-20"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-semibold">
          Unidad
          <select value={udmId} onChange={(e) => setUdmId(e.target.value)}>
            {unidades.map((u) => (
              <option key={u.id} value={u.id}>
                {u.nombre}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={crear}
          disabled={!nombre.trim() || !udmId}
          className="rounded bg-primary px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50"
        >
          Crear receta
        </button>
        {onCancelar && (
          <button
            type="button"
            onClick={onCancelar}
            className="px-2 py-1.5 text-xs text-gray"
          >
            Cancelar
          </button>
        )}
      </div>
      {recetas.length > 0 && (
        <label className="flex flex-col gap-1 text-xs font-semibold">
          ...o reusar una existente
          <select
            defaultValue=""
            onChange={(e) => e.target.value && onCreada(e.target.value)}
            className="min-w-56"
          >
            <option value="">Elegir receta...</option>
            {recetas.map((r) => (
              <option key={r.id} value={r.id}>
                {r.nombre}
              </option>
            ))}
          </select>
        </label>
      )}
      {error && (
        <p role="alert" className="text-sm font-semibold text-secondary">
          {error}
        </p>
      )}
    </div>
  );
}
