"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorApi } from "@/lib/cliente-api";
import {
  apiKds,
  ETIQUETA_ESTADO,
  marcarPreparado,
  type ItemCola,
  type PedidoCola,
} from "@/lib/kds";

/**
 * Cada cuánto se relee la cola. El estado real vive en el backend
 * (`venta_item.estado_preparacion`), así que este intervalo es lo que tarda
 * una pantalla en enterarse de lo que hizo otra: 3 s es imperceptible en
 * cocina y son ~20 requests/minuto por tablet, nada para esta API.
 * El push en vivo (WebSocket/Redis) es deuda declarada en `ROADMAP.md`.
 */
const REFRESCO_MS = 3000;

type Props = {
  pantalla: { id: string; nombre: string; tipo: "preparacion" | "despacho" };
  puedeEntregar: boolean;
};

export default function KdsCliente({ pantalla, puedeEntregar }: Props) {
  const [pedidos, setPedidos] = useState<PedidoCola[]>([]);
  const [aviso, setAviso] = useState<string | null>(null);
  const [cargado, setCargado] = useState(false);
  // Ítems con una llamada en vuelo: sin esto, dos toques seguidos mandan dos
  // avances y el segundo revienta contra la secuencia estricta del backend.
  const [enCurso, setEnCurso] = useState<Set<string>>(new Set());

  const refrescar = useCallback(async () => {
    try {
      setPedidos(await apiKds.cola(pantalla.id));
    } catch (e) {
      setAviso(e instanceof ErrorApi ? e.message : "Sin conexión con la API");
    } finally {
      setCargado(true);
    }
  }, [pantalla.id]);

  useEffect(() => {
    refrescar();
    const id = setInterval(() => {
      // Tablet con la pantalla apagada o el navegador en otra pestaña: no
      // tiene sentido seguir pidiendo la cola.
      if (!document.hidden) refrescar();
    }, REFRESCO_MS);
    // Al volver a mirar la pantalla, la cola puede llevar horas congelada:
    // esperar al siguiente tick mostraría pedidos viejos durante 3 s.
    const alVolver = () => {
      if (!document.hidden) refrescar();
    };
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", alVolver);
    };
  }, [refrescar]);

  useEffect(() => {
    if (!aviso) return;
    const id = setTimeout(() => setAviso(null), 4000);
    return () => clearTimeout(id);
  }, [aviso]);

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
    if (item.estado === "listo" || item.estado === "entregado") {
      setAviso("Ya está marcado. El avance no se puede deshacer (RN-CUP-002).");
      return;
    }
    setEnCurso((s) => new Set(s).add(item.venta_item_id));
    pintarListo([item.venta_item_id]);
    try {
      await marcarPreparado(item);
    } catch (e) {
      setAviso(e instanceof ErrorApi ? e.message : "No se pudo marcar el ítem");
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
    const faltan = pedido.items.filter(
      (i) => i.estado === "pendiente" || i.estado === "en_preparacion",
    );
    if (faltan.length === 0) return;
    pintarListo(faltan.map((i) => i.venta_item_id));
    try {
      for (const item of faltan) await marcarPreparado(item);
    } catch (e) {
      setAviso(e instanceof ErrorApi ? e.message : "No se pudo marcar el pedido");
    } finally {
      refrescar();
    }
  };

  const entregar = async (pedido: PedidoCola) => {
    try {
      await apiKds.entregar(pedido.venta_id);
      setAviso(`Pedido #${pedido.numero_orden} entregado`);
    } catch (e) {
      setAviso(e instanceof ErrorApi ? e.message : "No se pudo registrar la entrega");
    } finally {
      refrescar();
    }
  };

  return (
    <main className="kds">
      <header className="kds-top">
        <div className="kds-marca">
          <strong>{pantalla.nombre}</strong>
          <small>{pantalla.tipo === "despacho" ? "Despacho" : "Preparación"}</small>
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
                  const hecho = item.estado === "listo" || item.estado === "entregado";
                  return (
                    <li key={item.venta_item_id}>
                      <button
                        type="button"
                        className={`kds-item ${hecho ? "hecho" : item.estado}`}
                        aria-pressed={hecho}
                        onClick={() => tachar(item)}
                      >
                        <span className="kds-cant">{Number(item.cantidad)}</span>
                        <span className="kds-nombre">{item.producto}</span>
                        <span className="kds-check">{hecho ? "✓" : ""}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
              <footer className="kds-acciones">
                {pedido.items.some((i) => i.estado !== "listo" && i.estado !== "entregado") && (
                  <button type="button" className="kds-boton" onClick={() => tacharTodo(pedido)}>
                    Todo listo
                  </button>
                )}
                {pantalla.tipo === "despacho" &&
                  puedeEntregar &&
                  pedido.estado_pedido === "listo" && (
                    <button
                      type="button"
                      className="kds-boton pri"
                      onClick={() => entregar(pedido)}
                    >
                      Entregar
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
