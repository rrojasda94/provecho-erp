"use client";

import Link from "next/link";

import { useState } from "react";

import {
  ETIQUETA_ESTADO,
  apiKds,
  marcarPreparado,
  siguienteToque,
  type ItemCola,
  type PedidoCola,
  type Semaforo,
} from "@/lib/kds";

import NombreDeLinea from "./nombre-linea";
import { Espera, coloresDe, nivelDelPedido } from "./semaforo";
import { useCola } from "./use-cola";

type Props = {
  pantalla: { id: string; nombre: string; orden: number };
  sucursalId: string;
  semaforo: Semaforo;
};

/**
 * ¿Esta estación ya terminó con la línea? Es `listo` (salió de cocina) o se
 * la mandó al eslabón siguiente (ADR-044). Se compara contra el `orden` de
 * la pantalla y no contra el nombre de la estación: dos pantallas pueden
 * compartir eslabón, y renombrar una no puede cambiar lo que se tacha.
 */
function terminado(item: ItemCola, orden: number): boolean {
  return (
    item.estado === "listo" || item.estado === "entregado" || item.etapa_kds > orden
  );
}

export default function KdsCliente({ pantalla, sucursalId, semaforo }: Props) {
  const { pedidos, setPedidos, aviso, setAviso, avisarDe, cargado, refrescar } =
    useCola(pantalla.id);
  // Ítems con una llamada en vuelo: sin esto, dos toques seguidos mandan dos
  // avances y el segundo revienta contra la secuencia estricta del backend.
  const [enCurso, setEnCurso] = useState<Set<string>>(new Set());

  /** Pinta el cambio de una vez en la tarjeta y deja que el refresco confirme
   * contra el servidor: el cocinero necesita ver el resultado en el toque, no
   * en el siguiente ciclo de polling. */
  const pintar = (ids: string[], estado: ItemCola["estado"]) =>
    setPedidos((previos) =>
      previos.map((p) => ({
        ...p,
        items: p.items.map((i) => (ids.includes(i.venta_item_id) ? { ...i, estado } : i)),
      })),
    );

  /**
   * Corre una operación sobre una o más líneas con el guard de "en vuelo"
   * puesto. Lo comparten el toque, el deshacer y el "Todo listo": tres
   * caminos que mandan requests sobre los mismos ítems. `tacharTodo` no lo
   * tenía y un toque individual concurrente disparaba dos avances, el
   * segundo contra la secuencia estricta del backend.
   */
  const conGuard = async (
    ids: string[],
    operar: () => Promise<unknown>,
    falla: string,
  ) => {
    if (ids.some((id) => enCurso.has(id))) return;
    setEnCurso((s) => new Set([...s, ...ids]));
    try {
      await operar();
    } catch (e) {
      avisarDe(e, falla);
    } finally {
      setEnCurso((s) => new Set([...s].filter((id) => !ids.includes(id))));
      refrescar();
    }
  };

  /**
   * Un toque = **un** paso (2026-08-26). El primero marca la línea en
   * preparación; el segundo es el que la manda a la pantalla siguiente.
   *
   * Antes un solo toque encadenaba los dos y despachaba el plato: en cocina,
   * el roce de un delantal contra la tablet bastaba para mandar a la estación
   * siguiente algo que nadie había empezado.
   */
  const tocar = async (item: ItemCola) => {
    const destino = siguienteToque(item.estado);
    if (terminado(item, pantalla.orden) || destino === null) {
      setAviso("Ya salió de esta estación. Usa «Deshacer» si fue un error.");
      return;
    }
    pintar([item.venta_item_id], destino);
    await conGuard(
      [item.venta_item_id],
      () => apiKds.avanzar(item.venta_item_id, destino),
      "No se pudo marcar el ítem",
    );
  };

  /** Deshace el último toque: el estado vuelve atrás, o la línea regresa de
   * la estación a la que se la mandó por error (RN-CUP-002, enmendada). */
  const deshacer = (item: ItemCola) =>
    conGuard(
      [item.venta_item_id],
      () => apiKds.retroceder(item.venta_item_id),
      "No se pudo deshacer",
    );

  /** Equivalente al "click en la tarjeta" de Odoo: todo lo que falta, listo.
   * Sigue haciendo los dos pasos de una — es el atajo deliberado, el de quien
   * sí terminó el pedido entero. */
  const tacharTodo = async (pedido: PedidoCola) => {
    const faltan = pedido.items.filter((i) => !terminado(i, pantalla.orden));
    const ids = faltan.map((i) => i.venta_item_id);
    if (ids.length === 0) return;
    pintar(ids, "listo");
    await conGuard(
      ids,
      async () => {
        for (const item of faltan) await marcarPreparado(item);
      },
      "No se pudo marcar el pedido",
    );
  };

  return (
    <main className="kds" style={coloresDe(semaforo)}>
      <header className="kds-top">
        <div className="kds-marca">
          <strong>{pantalla.nombre}</strong>
          <small>Preparación</small>
        </div>
        <span className="kds-spacer" />
        <span className="kds-meta">
          {pedidos.length} {pedidos.length === 1 ? "pedido" : "pedidos"}
        </span>
        <a
          className="kds-cambiar"
          href={`/kds?pantalla=${pantalla.id}&sucursal=${sucursalId}&vista=historial`}
        >
          Historial
        </a>
        <a className="kds-cambiar" href={`/kds?sucursal=${sucursalId}`}>
          Estaciones
        </a>
        {/* La salida de la pantalla completa. Sin esto, quien entraba al
            KDS desde el lanzador de módulos quedaba encerrado: los demás
            enlaces cruzan entre pantallas de cocina y ninguno vuelve al
            resto del ERP, así que la única salida era el botón atrás del
            navegador o teclear la URL. */}
        <Link className="kds-salir" href="/">
          Salir
        </Link>
      </header>

      {pedidos.length === 0 ? (
        <p className="kds-nada">
          {cargado ? "Sin pedidos en cola." : "Cargando la cola…"}
        </p>
      ) : (
        <section className="kds-grid">
          {pedidos.map((pedido) => (
            <article
              // La clave es el par, no la venta: una mesa que pidió tres
              // veces son tres tarjetas de la misma orden (ADR-075).
              key={`${pedido.venta_id}-${pedido.tanda}`}
              className={`kds-card ${pedido.estado_pedido} nivel-${nivelDelPedido(pedido, semaforo)}`}
            >
              <header>
                <span className="kds-orden">
                  #{pedido.numero_orden}
                  {/* La primera tanda no se rotula: es el pedido. Las
                      siguientes sí, o dos tarjetas con el mismo número se
                      leerían como un duplicado. */}
                  {pedido.tanda > 1 && (
                    <small className="kds-tanda"> · aumento {pedido.tanda - 1}</small>
                  )}
                </span>
                <span className="kds-ref">{pedido.referencia_atencion ?? "—"}</span>
                <Espera pedido={pedido} semaforo={semaforo} />
                <span className="kds-badge">{ETIQUETA_ESTADO[pedido.estado_pedido]}</span>
              </header>
              <small className="kds-canal">
                {pedido.modalidad} · {pedido.canal}
              </small>
              {pedido.tipo === "consumo_personal" && (
                <small className="kds-consumo">Consumo de personal</small>
              )}
              <ul className="kds-items">
                {pedido.items.map((item) => (
                  <Linea
                    key={item.venta_item_id}
                    item={item}
                    orden={pantalla.orden}
                    onTocar={() => tocar(item)}
                    onDeshacer={() => deshacer(item)}
                  />
                ))}
              </ul>
              {/* Al pie y no arriba: primero se lee qué hay que preparar,
                  y después cómo sale. Arriba competiría con el número de
                  orden, que es lo que la cocina busca de un vistazo. */}
              {pedido.nota_cocina && (
                <p className="kds-nota-pedido">Al servir: {pedido.nota_cocina}</p>
              )}
              <footer className="kds-acciones">
                {pedido.items.some((i) => !terminado(i, pantalla.orden)) && (
                  <button
                    type="button"
                    className="kds-boton"
                    onClick={() => tacharTodo(pedido)}
                  >
                    Todo listo
                  </button>
                )}
              </footer>
            </article>
          ))}
        </section>
      )}

      {aviso && <div className="kds-aviso">{aviso}</div>}
    </main>
  );
}

/**
 * Una línea de la comanda. El botón de deshacer aparece en cuanto hay algo
 * que deshacer, no solo cuando la línea ya salió: el toque que más seguido
 * hay que corregir es el primero, el que la marcó en preparación sin que
 * nadie la hubiera empezado.
 */
function Linea({
  item,
  orden,
  onTocar,
  onDeshacer,
}: {
  item: ItemCola;
  orden: number;
  onTocar: () => void;
  onDeshacer: () => void;
}) {
  const hecho = terminado(item, orden);
  return (
    <li>
      <button
        type="button"
        className={`kds-item ${hecho ? "hecho" : item.estado}`}
        aria-pressed={hecho}
        onClick={onTocar}
      >
        <span className="kds-cant">{Number(item.cantidad)}</span>
        <NombreDeLinea item={item} />
        {/* Tachado y con destino: el cocinero necesita ver que lo suyo salió,
            y a dónde fue (ADR-044). */}
        <span className="kds-check">{hecho ? (item.estacion ?? "✓") : ""}</span>
      </button>
      {item.estado !== "pendiente" && (
        <button
          type="button"
          className="kds-deshacer"
          onClick={onDeshacer}
          aria-label={`Deshacer ${item.producto}`}
          title="Deshacer el último toque"
        >
          ↶
        </button>
      )}
    </li>
  );
}
