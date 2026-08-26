"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorApi } from "@/lib/cliente-api";
import { apiKds, type PedidoHistorial } from "@/lib/kds";

import NombreDeLinea from "./nombre-linea";

/**
 * Lo que esta pantalla ya despachó, del día de negocio.
 *
 * La cola descarta los pedidos entregados en cuanto se cierran, y hasta ahora
 * eso era todo lo que la cocina podía ver: si se entregó el pedido
 * equivocado, no había dónde ir a mirarlo —ni para confirmarlo ni para
 * corregirlo—. Acá están, con la hora y el botón para devolverlos a despacho.
 *
 * No hace polling. El historial no cambia solo: cambia cuando alguien
 * entrega, y para eso está la cola. Un `setInterval` acá sería tráfico para
 * mirar una lista que casi siempre es la misma.
 */

type Props = {
  pantalla: { id: string; nombre: string };
  sucursalId: string;
  puedeEntregar: boolean;
};

function hora(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" });
}

export default function HistorialCliente({ pantalla, sucursalId, puedeEntregar }: Props) {
  const [pedidos, setPedidos] = useState<PedidoHistorial[]>([]);
  const [aviso, setAviso] = useState<string | null>(null);
  const [cargado, setCargado] = useState(false);
  const [enCurso, setEnCurso] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try {
      setPedidos(await apiKds.historial(pantalla.id));
    } catch (e) {
      setAviso(e instanceof ErrorApi ? e.message : "Sin conexión con la API");
    } finally {
      setCargado(true);
    }
  }, [pantalla.id]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const devolver = async (pedido: PedidoHistorial) => {
    if (enCurso) return;
    setEnCurso(pedido.venta_id);
    try {
      await apiKds.deshacerEntrega(pedido.venta_id);
      setAviso(`Pedido #${pedido.numero_orden} devuelto a despacho`);
    } catch (e) {
      setAviso(e instanceof ErrorApi ? e.message : "No se pudo deshacer la entrega");
    } finally {
      setEnCurso(null);
      cargar();
    }
  };

  return (
    <main className="kds">
      <header className="kds-top">
        <div className="kds-marca">
          <strong>{pantalla.nombre}</strong>
          <small>Entregados hoy</small>
        </div>
        <span className="kds-spacer" />
        <span className="kds-meta">
          {pedidos.length} {pedidos.length === 1 ? "pedido" : "pedidos"}
        </span>
        <a
          className="kds-cambiar"
          href={`/kds?pantalla=${pantalla.id}&sucursal=${sucursalId}`}
        >
          Volver a la cola
        </a>
      </header>

      {pedidos.length === 0 ? (
        <p className="kds-nada">
          {cargado ? "Todavía no se entregó nada hoy." : "Cargando el historial…"}
        </p>
      ) : (
        <section className="kds-grid">
          {pedidos.map((pedido) => (
            <article key={pedido.venta_id} className="kds-card entregado">
              <header>
                <span className="kds-orden">#{pedido.numero_orden}</span>
                <span className="kds-ref">{pedido.referencia_atencion ?? "—"}</span>
                <span className="kds-badge">{hora(pedido.entregado_en)}</span>
              </header>
              <small className="kds-canal">
                {pedido.modalidad} · {pedido.canal}
              </small>
              <ul className="kds-items">
                {pedido.items.map((item) => (
                  <li key={item.venta_item_id}>
                    <div className="kds-item estatico hecho">
                      <span className="kds-cant">{Number(item.cantidad)}</span>
                      <NombreDeLinea item={item} />
                      <span className="kds-check">✓</span>
                    </div>
                  </li>
                ))}
              </ul>
              <footer className="kds-acciones">
                {/* Mismo permiso que entregar (RN-CUP-006): quien puede dar
                    por entregado un pedido es quien tiene que poder
                    corregirse. */}
                {puedeEntregar && (
                  <button
                    type="button"
                    className="kds-boton"
                    onClick={() => devolver(pedido)}
                    disabled={enCurso === pedido.venta_id}
                  >
                    No salió — devolver a despacho
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
