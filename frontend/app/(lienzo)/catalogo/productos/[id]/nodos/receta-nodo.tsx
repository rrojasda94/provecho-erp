"use client";

import { useRef, useState } from "react";

import {
  catalogoApi,
  type Articulo,
  type LineaDeAtributo,
  type RecetaDetalle,
  type RecetaItem,
} from "@/lib/catalogo";
import { ErrorApi } from "@/lib/cliente-api";
import { condicionLegible } from "@/lib/lienzo";
import { costoDeLineas, insumosLibres, lineasCondicionadasA, soles } from "@/lib/nodos";

/** El atributo y el valor que nombra cada `producto_atributo_valor`. */
type IndiceValores = Map<string, { atributo: string; valor: string }>;

/** El valor sobre el que se está trabajando, cuando el nodo es un `valor`. */
export type CondicionDelNodo = { ptavId: string; nombre: string };

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
 *
 * **Dos vistas, una receta.** Con `condicion` viene de un nodo de valor
 * ("Americana F") y se muestran solo las líneas condicionadas a ese valor,
 * que es lo que ese sabor aporta al plato; sin ella viene del tamaño y se
 * muestra la receta entera, cada línea con su condición al lado. Es la misma
 * receta mirada por dos lados, no dos recetas (RN-COM-037).
 */
export function RecetaDelNodo({
  titulo,
  receta,
  articulos,
  atributos,
  indice,
  condicion,
  onActualizada,
  onError,
}: {
  titulo: string;
  receta: RecetaDetalle | null;
  articulos: Articulo[];
  atributos: LineaDeAtributo[];
  indice: IndiceValores;
  condicion: CondicionDelNodo | null;
  onActualizada: (r: RecetaDetalle) => void;
  onError: (mensaje: string) => void;
}) {
  const [guardando, setGuardando] = useState(false);

  if (!receta) return <SinReceta titulo={titulo} condicion={condicion} />;

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

  // La condición que se pone al agregar: la del nodo de valor, o ninguna
  // (la línea aplica siempre) cuando se está mirando el tamaño.
  const aplicaValores = condicion ? [condicion.ptavId] : [];
  const lineas = condicion
    ? lineasCondicionadasA(receta.items, condicion.ptavId)
    : receta.items;

  return (
    <div className={`lienzo-receta${guardando ? " ocupado" : ""}`}>
      {condicion && (
        <p className="lienzo-nota">
          Lo que <strong>{condicion.nombre}</strong> pone en {receta.nombre}.
        </p>
      )}

      <table className="lienzo-tabla">
        <tbody>
          {lineas.length === 0 && (
            <tr>
              <td className="lienzo-nota">
                <Vacia condicion={condicion} />
              </td>
            </tr>
          )}
          {lineas.map((it) => (
            <FilaDeReceta
              key={it.id}
              item={it}
              receta={receta}
              atributos={atributos}
              indice={indice}
              // El chip solo en la vista del tamaño: en la del valor la
              // condición ya la dice el encabezado, y repetirla en cada fila
              // sería ruido.
              editable={condicion === null}
              correr={correr}
            />
          ))}
        </tbody>
      </table>

      <AgregarInsumo
        receta={receta}
        libres={insumosLibres(articulos, receta.items, aplicaValores)}
        aplicaValores={aplicaValores}
        guardando={guardando}
        correr={correr}
      />

      <PieDeCosto receta={receta} condicion={condicion} lineas={lineas} />
    </div>
  );
}

/** El nodo no tiene dónde guardar insumos. Un sabor no tiene receta propia:
 * sus líneas viven en la del tamaño, así que lo que falta no es la suya. */
function SinReceta({
  titulo,
  condicion,
}: {
  titulo: string;
  condicion: CondicionDelNodo | null;
}) {
  return (
    <p className="lienzo-nota">
      {condicion
        ? `${titulo} no tiene dónde guardar sus insumos: el tamaño elegido todavía no
           tiene receta. Se le asigna una desde la ficha del producto.`
        : `${titulo} no tiene receta todavía. Se le asigna una desde la ficha del
           producto.`}
    </p>
  );
}

function Vacia({ condicion }: { condicion: CondicionDelNodo | null }) {
  return condicion ? (
    <>Ninguna línea está condicionada a {condicion.nombre}. Agrega la primera.</>
  ) : (
    <>Receta vacía: agrega el primer insumo.</>
  );
}

/** El alta de una línea. La cantidad viaja como `expresion` aunque sea un
 * número pelado: el servidor la evalúa y redondea a la UdM del insumo. */
function AgregarInsumo({
  receta,
  libres,
  aplicaValores,
  guardando,
  correr,
}: {
  receta: RecetaDetalle;
  libres: Articulo[];
  aplicaValores: string[];
  guardando: boolean;
  correr: (accion: () => Promise<RecetaDetalle>) => Promise<void>;
}) {
  const [nuevo, setNuevo] = useState("");
  const [cantidad, setCantidad] = useState("");

  return (
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
        disabled={guardando || !nuevo || !cantidad.trim()}
        onClick={() =>
          correr(async () => {
            const r = await catalogoApi.agregarItem(receta.id, {
              articulo_id: nuevo,
              expresion: cantidad.trim(),
              aplica_valores: aplicaValores,
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
  );
}

/** En la vista de un sabor el costo que importa es el de **sus** líneas; el
 * de la receta entera se deja al lado para no perder la referencia. */
function PieDeCosto({
  receta,
  condicion,
  lineas,
}: {
  receta: RecetaDetalle;
  condicion: CondicionDelNodo | null;
  lineas: RecetaItem[];
}) {
  const entera = Number(receta.costo_total);
  if (!condicion) {
    return (
      <p className="lienzo-nota">
        Costo de la receta: <strong>{soles(entera)}</strong> · rinde{" "}
        {receta.rendimiento_cantidad} {receta.rendimiento_unidad_medida_nombre ?? ""}
      </p>
    );
  }
  return (
    <p className="lienzo-nota">
      Costo de estas líneas:{" "}
      <strong>{soles(costoDeLineas(lineas, Number(receta.rendimiento_cantidad)))}</strong>{" "}
      · la receta entera cuesta {soles(entera)}
    </p>
  );
}

/** Una línea: el insumo, su condición, la cantidad tecleada y el costo.
 * Vive aparte para que el editor no cruce el límite de complejidad del repo,
 * igual que `Inspector` se partió en `DetalleDelPlato` / `Pestanas`. */
function FilaDeReceta({
  item,
  receta,
  atributos,
  indice,
  editable,
  correr,
}: {
  item: RecetaItem;
  receta: RecetaDetalle;
  atributos: LineaDeAtributo[];
  indice: IndiceValores;
  editable: boolean;
  correr: (accion: () => Promise<RecetaDetalle>) => Promise<void>;
}) {
  return (
    <tr>
      <td>
        {item.articulo_nombre}
        <span className="origen">
          {item.unidad_medida_nombre}
          {Number(item.merma_pct) > 0 ? ` · merma ${item.merma_pct}%` : ""}
        </span>
        {editable ? (
          <ChipDeCondicion
            item={item}
            receta={receta}
            atributos={atributos}
            indice={indice}
            correr={correr}
          />
        ) : null}
      </td>
      <td className="num">
        <input
          className="lienzo-cantidad"
          defaultValue={item.expresion ?? item.cantidad}
          aria-label={`Cantidad de ${item.articulo_nombre}`}
          title="Acepta operaciones: 1000/3, 250*1.5"
          onBlur={(e) => {
            const v = e.target.value.trim();
            if (!v || v === (item.expresion ?? item.cantidad)) return;
            // Se manda como `expresion` siempre: el servidor la evalúa y
            // redondea a la UdM del insumo. Mandar el resultado calculado
            // acá sería una segunda verdad.
            correr(() => catalogoApi.editarItem(receta.id, item.id, { expresion: v }));
          }}
        />
      </td>
      <td className="num">{soles(Number(item.costo_linea))}</td>
      <td className="num">
        <button
          type="button"
          className="nodo-accion riesgo"
          aria-label={`Quitar ${item.articulo_nombre} de la receta`}
          onClick={() => correr(() => catalogoApi.eliminarItem(receta.id, item.id))}
        >
          ×
        </button>
      </td>
    </tr>
  );
}

/**
 * A qué combinaciones aplica la línea (RN-COM-037), editable.
 *
 * `<details>` con casillas y no un `<select multiple>`: dieciocho opciones
 * sin agrupar por atributo no se pueden leer, y agruparlas pide `<optgroup>`
 * más `Ctrl+click`, que nadie descubre. HTML plano, accesible por teclado,
 * sin librería nueva — el mismo criterio de ADR-057 §1.
 *
 * **Se guarda con "Aplicar" y no en cada casilla**, aunque el resto del
 * lienzo guarde en cada `onBlur`. Acá el estado intermedio puede ser
 * inválido: destildar los cuatro sabores de una mitad para tildar otros
 * cuatro pasa por "Siempre", y si ya existe una línea sin condición del
 * mismo insumo el servidor devuelve 409 con la mitad del cambio hecho. Un
 * solo PATCH no deja nada a medias.
 */
function ChipDeCondicion({
  item,
  receta,
  atributos,
  indice,
  correr,
}: {
  item: RecetaItem;
  receta: RecetaDetalle;
  atributos: LineaDeAtributo[];
  indice: IndiceValores;
  correr: (accion: () => Promise<RecetaDetalle>) => Promise<void>;
}) {
  const [borrador, setBorrador] = useState<string[] | null>(null);
  const caja = useRef<HTMLDetailsElement>(null);
  const elegidos = borrador ?? item.aplica_valores;

  // Sin atributos declarados no hay condición posible: se muestra el texto
  // sin el desplegable, que estaría vacío.
  if (atributos.length === 0) {
    return item.aplica_valores.length === 0 ? null : (
      <span className="lienzo-condicion-texto">
        {condicionLegible(item.aplica_valores, indice)}
      </span>
    );
  }

  const guardar = (valores: string[]) =>
    correr(async () => {
      const r = await catalogoApi.editarItem(receta.id, item.id, {
        aplica_valores: valores,
      });
      setBorrador(null);
      // Se cierra al guardar: el resumen pasa a decir la condición nueva, y
      // eso —y no un cartel— es la señal de que el servidor la aceptó.
      if (caja.current) caja.current.open = false;
      return r;
    });

  return (
    <details
      ref={caja}
      className="lienzo-condicion"
      onToggle={(e) => {
        // Cerrar sin aplicar descarta el borrador: lo que vale es lo que
        // devolvió el servidor.
        if (!(e.currentTarget as HTMLDetailsElement).open) setBorrador(null);
      }}
    >
      <summary title={`Condición de ${item.articulo_nombre}`}>
        {condicionLegible(item.aplica_valores, indice)}
      </summary>
      {atributos.map((linea) => (
        <fieldset key={linea.linea_id}>
          <legend>{linea.nombre}</legend>
          {linea.valores
            .filter((v) => v.activo)
            .map((v) => (
              <label key={v.id}>
                <input
                  type="checkbox"
                  checked={elegidos.includes(v.id)}
                  onChange={(e) =>
                    setBorrador(
                      e.target.checked
                        ? [...elegidos, v.id]
                        : elegidos.filter((id) => id !== v.id),
                    )
                  }
                />
                {v.nombre}
              </label>
            ))}
        </fieldset>
      ))}
      <div className="lienzo-condicion-acciones">
        <button type="button" className="lienzo-boton" onClick={() => guardar(elegidos)}>
          Aplicar
        </button>
        <button type="button" className="nodo-accion" onClick={() => guardar([])}>
          Siempre
        </button>
      </div>
    </details>
  );
}
