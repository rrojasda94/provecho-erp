"use client";

import { useState } from "react";

import { ETIQUETA_ESTADO, marcarPreparado, type ItemCola, type PedidoCola } from "@/lib/kds";

import { useCola } from "./use-cola";

type Props = {
  pantalla: { id: string; nombre: string; orden: number };
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

export default function KdsCliente({ pantalla }: Props) {
  const { pedidos, setPedidos, aviso, setAviso, avisarDe, cargado, refrescar } =
    useCola(pantalla.id);
  // Ítems con una llamada en vuelo: sin esto, dos toques seguidos mandan dos
  // avances y el segundo revienta contra la secuencia estricta del backend.
  const [enCurso, setEnCurso] = useState<Set<string>>(new Set());

  /** Pinta el avance de una vez en la tarjeta y deja que el refresco confirme
   * contra el servidor: el cocinero necesita ver el tachado en el toque, no
   * en el siguiente ciclo de polling. */
  const pintarListo = (ids: string[]) =>
    setPedidos((previos) =>
      previos.map((p) => ({
        ...p,
        items: p.items.map((i) =>
          ids.includes(i.venta_item_id) ? { ...i, estado: "listo" as const } : i,
        ),
      })),
    );

  const tachar = async (item: ItemCola) => {
    if (enCurso.has(item.venta_item_id)) return;
    if (terminado(item, pantalla.orden)) {
      setAviso("Ya está marcado. El avance no se puede deshacer (RN-CUP-002).");
      return;
    }
    setEnCurso((s) => new Set(s).add(item.venta_item_id));
    pintarListo([item.venta_item_id]);
    try {
      await marcarPreparado(item);
    } catch (e) {
      avisarDe(e, "No se pudo marcar el ítem");
    } finally {
      setEnCurso((s) => {
        const copia = new Set(s);
        copia.delete(item.venta_item_id);
        return copia;
      });
      refrescar();
    }
  };

  /** Equivalente al "click en la tarjeta" de Odoo: todo lo que falta, listo. */
  const tacharTodo = async (pedido: PedidoCola) => {
    const faltan = pedido.items.filter((i) => !terminado(i, pantalla.orden));
    if (faltan.length === 0) return;
    pintarListo(faltan.map((i) => i.venta_item_id));
    try {
      for (const item of faltan) await marcarPreparado(item);
    } catch (e) {
      avisarDe(e, "No se pudo marcar el pedido");
    } finally {
      refrescar();
    }
  };

  return (
    <main className="kds">
      <header className="kds-top">
        <div className="kds-marca">
          <strong>{pantalla.nombre}</strong>
          <small>Preparación</small>
        </div>
        <span className="kds-spacer" />
        <span className="kds-meta">
          {pedidos.length} {pedidos.length === 1 ? "pedido" : "pedidos"}
        </span>
        <a className="kds-cambiar" href="/kds">
          Estaciones
        </a>
      </header>

      {pedidos.length === 0 ? (
        <p className="kds-nada">
          {cargado ? "Sin pedidos en cola." : "Cargando la cola…"}
        </p>
      ) : (
        <section className="kds-grid">
          {pedidos.map((pedido) => (
            <article key={pedido.venta_id} className={`kds-card ${pedido.estado_pedido}`}>
              <header>
                <span className="kds-orden">#{pedido.numero_orden}</span>
                <span className="kds-ref">{pedido.referencia_atencion ?? "—"}</span>
                <span className="kds-badge">{ETIQUETA_ESTADO[pedido.estado_pedido]}</span>
              </header>
              <small className="kds-canal">
                {pedido.modalidad} · {pedido.canal}
              </small>
              {pedido.tipo === "consumo_personal" && (
                <small className="kds-consumo">Consumo de personal</small>
              )}
              <ul className="kds-items">
                {pedido.items.map((item) => {
                  const hecho = terminado(item, pantalla.orden);
                  return (
                    <li key={item.venta_item_id}>
                      <button
                        type="button"
                        className={`kds-item ${hecho ? "hecho" : item.estado}`}
                        aria-pressed={hecho}
                        onClick={() => tachar(item)}
                      >
                        <span className="kds-cant">{Number(item.cantidad)}</span>
                        <span className="kds-nombre">
                          {item.producto}
                          {/* Las restas van DENTRO del nombre y en rojo: en
                              una pantalla que se lee de reojo, un "sin
                              cebolla" que pasa desapercibido sale como plato
                              rehecho (RN-COM-028). */}
                          {item.sin?.map((insumo) => (
                            <em key={insumo} className="kds-sin">
                              SIN {insumo.toUpperCase()}
                            </em>
                          ))}
                        </span>
                        {/* Tachado y con destino: el cocinero necesita ver que
                            lo suyo salió, y a dónde fue (ADR-044). */}
                        <span className="kds-check">
                          {hecho ? (item.estacion ?? "✓") : ""}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
              <footer className="kds-acciones">
                {pedido.items.some((i) => !terminado(i, pantalla.orden)) && (
                  <button type="button" className="kds-boton" onClick={() => tacharTodo(pedido)}>
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
