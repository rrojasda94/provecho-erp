"use client";

import {
  ETIQUETA_ESTADO,
  apiKds,
  type ItemCola,
  type PedidoCola,
  type Semaforo,
} from "@/lib/kds";

import NombreDeLinea from "./nombre-linea";
import { Espera, coloresDe, nivelDelPedido } from "./semaforo";
import { useCola } from "./use-cola";

/**
 * Pantalla de despacho. No cocina: arma y entrega, así que muestra cosas
 * distintas de una estación aunque lea la misma cola.
 *
 * La unidad es el PEDIDO y no la línea (ADR-044): despacho no decide qué
 * plato sale antes, decide si el pedido ya se puede llevar. Por eso cada
 * tarjeta dice cuánto le falta y —lo que antes no se veía— POR QUIÉN está
 * esperando: "2 de 3, falta el horno" es accionable, "en preparación" no.
 *
 * Tampoco tacha ítems: marcar preparado es un acto de la estación que lo
 * preparó (RN-CUP-003). Desde acá solo se entrega.
 */

type Props = {
  pantalla: { id: string; nombre: string };
  sucursalId: string;
  puedeEntregar: boolean;
  semaforo: Semaforo;
};

/** Estaciones por las que el pedido todavía espera, sin repetir. */
function pendientesPor(items: ItemCola[]): string[] {
  return [...new Set(items.map((i) => i.estacion).filter((e): e is string => !!e))];
}

function listos(items: ItemCola[]): number {
  return items.filter((i) => i.estado === "listo" || i.estado === "entregado").length;
}

function Tarjeta({
  pedido,
  puedeEntregar,
  semaforo,
  onEntregar,
}: {
  pedido: PedidoCola;
  puedeEntregar: boolean;
  semaforo: Semaforo;
  onEntregar: () => void;
}) {
  const faltan = pendientesPor(pedido.items);
  const completo = pedido.estado_pedido === "listo";
  return (
    <article
      className={`kds-card ${pedido.estado_pedido} nivel-${nivelDelPedido(pedido, semaforo)}`}
    >
      <header>
        <span className="kds-orden">#{pedido.numero_orden}</span>
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

      <p className="kds-avance">
        <strong>
          {listos(pedido.items)} de {pedido.items.length}
        </strong>{" "}
        {/* Sin estaciones pendientes y sin estar completo: hay una línea de
            una categoría que ninguna estación atiende, así que nadie la va a
            preparar. Decirlo es lo único que permite arreglarlo — callarlo
            deja el pedido colgado sin explicación. */}
        {completo
          ? "— listo para entregar"
          : faltan.length
            ? `— falta ${faltan.join(", ")}`
            : "— hay líneas sin estación asignada: revisa las categorías de las estaciones"}
      </p>

      <ul className="kds-items">
        {pedido.items.map((item) => {
          const hecho = !item.estacion;
          return (
            <li key={item.venta_item_id}>
              {/* Sin botón: despacho mira, no tacha. */}
              <div className={`kds-item estatico ${hecho ? "hecho" : ""}`}>
                <span className="kds-cant">{Number(item.cantidad)}</span>
                <NombreDeLinea item={item} />
                <span className={`kds-estacion ${hecho ? "hecho" : ""}`}>
                  {item.estacion ?? "Listo"}
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      <footer className="kds-acciones">
        {puedeEntregar && completo && (
          <button type="button" className="kds-boton pri" onClick={onEntregar}>
            Entregar
          </button>
        )}
      </footer>
    </article>
  );
}

export default function DespachoCliente({
  pantalla,
  sucursalId,
  puedeEntregar,
  semaforo,
}: Props) {
  const { pedidos, aviso, setAviso, avisarDe, cargado, refrescar } = useCola(pantalla.id);

  const entregar = async (pedido: PedidoCola) => {
    try {
      await apiKds.entregar(pedido.venta_id);
      setAviso(`Pedido #${pedido.numero_orden} entregado`);
    } catch (e) {
      avisarDe(e, "No se pudo registrar la entrega");
    } finally {
      refrescar();
    }
  };

  return (
    <main className="kds" style={coloresDe(semaforo)}>
      <header className="kds-top">
        <div className="kds-marca">
          <strong>{pantalla.nombre}</strong>
          <small>Despacho</small>
        </div>
        <span className="kds-spacer" />
        <span className="kds-meta">
          {pedidos.length} {pedidos.length === 1 ? "pedido" : "pedidos"}
        </span>
        {/* Lo que ya salió, con la vuelta atrás para el toque sobre la
            tarjeta equivocada. */}
        <a
          className="kds-cambiar"
          href={`/kds?pantalla=${pantalla.id}&sucursal=${sucursalId}&vista=historial`}
        >
          Historial
        </a>
        <a className="kds-cambiar" href={`/kds?sucursal=${sucursalId}`}>
          Estaciones
        </a>
      </header>

      {pedidos.length === 0 ? (
        <p className="kds-nada">
          {cargado ? "Nada por despachar." : "Cargando la cola…"}
        </p>
      ) : (
        <section className="kds-grid">
          {pedidos.map((pedido) => (
            <Tarjeta
              key={pedido.venta_id}
              pedido={pedido}
              puedeEntregar={puedeEntregar}
              semaforo={semaforo}
              onEntregar={() => entregar(pedido)}
            />
          ))}
        </section>
      )}

      {aviso && <div className="kds-aviso">{aviso}</div>}
    </main>
  );
}
