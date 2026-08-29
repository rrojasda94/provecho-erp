"use client";

import Link from "next/link";

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
  /** Sin los enlaces a Historial y Estaciones. Lo usa el despacho embebido
   * en el PDV: desde un overlay, un enlace que navega fuera es una trampa —
   * el cajero pierde de vista la caja y el pedido a medio armar. */
  sinNavegacion?: boolean;
};

/** Estaciones por las que el pedido todavía espera, sin repetir. */
function pendientesPor(items: ItemCola[]): string[] {
  return [...new Set(items.map((i) => i.estacion).filter((e): e is string => !!e))];
}

/**
 * ¿Esta línea ya se preparó?
 *
 * Lo dice su `estado` y no la ausencia de estación. Eran dos cosas distintas
 * que se leían como una: una línea de una categoría que ninguna estación
 * atendía tampoco tenía estación, así que se pintaba en verde y rotulada
 * "Listo" mientras seguía `pendiente` — el pedido de la foto decía "2 de 4"
 * con las cuatro líneas tachadas. Al mozo se le estaba diciendo que llevara
 * comida que nadie había hecho.
 */
function estaListo(item: ItemCola): boolean {
  return item.estado === "listo" || item.estado === "entregado";
}

function listos(items: ItemCola[]): number {
  return items.filter(estaListo).length;
}

/**
 * Lo ya preparado primero, en el orden en que quedó dentro de cada bloque.
 *
 * Despacho arma la bolsa: ver de un vistazo qué ya puede salir es la mitad
 * del trabajo, y en una comanda larga lo listo quedaba salpicado entre lo
 * que todavía falta.
 */
function listosPrimero(items: ItemCola[]): ItemCola[] {
  return [...items.filter(estaListo), ...items.filter((i) => !estaListo(i))];
}

/**
 * Qué le falta al pedido, en una frase.
 *
 * Sin estaciones pendientes y sin estar completo: hay una línea de una
 * categoría que ninguna estación atiende. Desde ADR-078 eso ya no le pasa a
 * un pedido nuevo —la primera estación se hace cargo—, pero los que quedaron
 * así siguen en la cola y callarlo los dejaría colgados sin explicación.
 */
function faltaEnPedido(completo: boolean, faltan: string[]): string {
  if (completo) return "— listo para entregar";
  if (faltan.length) return `— falta ${faltan.join(", ")}`;
  return "— hay líneas sin estación asignada: revisa las categorías de las estaciones";
}

/** Cuánto del pedido está hecho y por quién espera. */
function Avance({ pedido, completo }: { pedido: PedidoCola; completo: boolean }) {
  const yaListas = listos(pedido.items);
  return (
    <>
      <p className="kds-avance">
        <strong>
          {yaListas} de {pedido.items.length}
        </strong>{" "}
        {faltaEnPedido(completo, pendientesPor(pedido.items))}
      </p>

      {/* Lo que ya se puede llevar, cuando el pedido todavía no está entero.
          El mozo no entrega media orden (ADR-044) pero sí necesita saber qué
          hay hecho: sin esto tenía que contar las líneas tachadas a ojo. */}
      {!completo && yaListas > 0 && (
        <p className="kds-avance-parcial">
          {yaListas} {yaListas === 1 ? "línea lista" : "líneas listas"}
        </p>
      )}
    </>
  );
}

/** Las líneas del pedido, lo ya preparado primero. Componente aparte para
 * que la tarjeta no cargue con el detalle de cada fila. */
function Lineas({ items }: { items: ItemCola[] }) {
  return (
    <ul className="kds-items">
      {listosPrimero(items).map((item) => {
        const hecho = estaListo(item);
        return (
          <li key={item.venta_item_id}>
            {/* Sin botón: despacho mira, no tacha. */}
            <div className={`kds-item estatico ${hecho ? "hecho" : ""}`}>
              <span className="kds-cant">{Number(item.cantidad)}</span>
              <NombreDeLinea item={item} />
              {/* Ya listo dice "Listo"; si sigue pendiente y sin estación es
                  que ninguna atiende su categoría. Antes las dos cosas se
                  leían igual y la segunda salía tachada en verde. */}
              <span className={`kds-estacion ${hecho ? "hecho" : ""}`}>
                {hecho ? "Listo" : (item.estacion ?? "Sin estación")}
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
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
      {/* Solo delivery: en mesa o para llevar no hay dirección que mirar. */}
      {pedido.modalidad === "delivery" && pedido.direccion_entrega && (
        <p className="kds-direccion">{pedido.direccion_entrega}</p>
      )}

      <Avance pedido={pedido} completo={completo} />

      <Lineas items={pedido.items} />

      {/* Despacho también la lee: es quien arma la bolsa, y "bebidas al
          final" es una instrucción de armado antes que de cocina. */}
      {pedido.nota_cocina && (
        <p className="kds-nota-pedido">Al servir: {pedido.nota_cocina}</p>
      )}

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
  sinNavegacion = false,
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
        {!sinNavegacion && (
          <>
            <a
              className="kds-cambiar"
              href={`/kds?pantalla=${pantalla.id}&sucursal=${sucursalId}&vista=historial`}
            >
              Historial
            </a>
            <a className="kds-cambiar" href={`/kds?sucursal=${sucursalId}`}>
              Estaciones
            </a>
            {/* La salida de la pantalla completa. Va dentro de
                `sinNavegacion` como los otros: desde el overlay del PDV el
                despacho se cierra con su ×, que devuelve al pedido a medio
                armar en vez de navegar fuera y descartarlo. */}
            <Link className="kds-salir" href="/">
              Salir
            </Link>
          </>
        )}
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
