"use client";

import { useMemo, useState } from "react";

import { soles, type ItemDeCarta, type MesaEnMapa, type Venta } from "@/lib/pdv";

type Vista = "catalogo" | "mesas" | "cobrados";
const TODAS = "__todas__";

type Props = {
  carta: ItemDeCarta[];
  mesas: MesaEnMapa[];
  cobrados: Venta[];
  abiertas: Venta[];
  vista: Vista;
  onVista: (v: Vista) => void;
  onProducto: (item: ItemDeCarta) => void;
  onMesa: (mesa: MesaEnMapa) => void;
  onOrdenAbierta: (venta: Venta) => void;
  onVerCobrado: (venta: Venta) => void;
};

/** Panel izquierdo: qué se vende, cómo está el salón y qué se cobró hoy. */
export default function Catalogo(props: Props) {
  const { carta, mesas, cobrados, abiertas, vista, onVista, onProducto, onMesa } =
    props;
  const [busqueda, setBusqueda] = useState("");
  const [categoria, setCategoria] = useState(TODAS);

  const categorias = useMemo(() => {
    const vistas = new Map<string, string>();
    for (const p of carta) {
      if (p.categoria_id) vistas.set(p.categoria_id, p.categoria_nombre ?? "Sin nombre");
    }
    return Array.from(vistas, ([id, nombre]) => ({ id, nombre }));
  }, [carta]);

  const visibles = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return carta.filter((p) => {
      if (categoria !== TODAS && p.categoria_id !== categoria) return false;
      return q ? p.nombre.toLowerCase().includes(q) : true;
    });
  }, [carta, busqueda, categoria]);

  return (
    <section className="pdv-izq">
      <div className="pdv-barra">
        <input
          className="pdv-buscar"
          type="search"
          placeholder="Buscar producto"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
        />
        <div className="pdv-seg" role="group" aria-label="Vista">
          {(["catalogo", "mesas", "cobrados"] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={vista === v}
              onClick={() => onVista(v)}
            >
              {v === "catalogo" ? "Catálogo" : v === "mesas" ? "Mesas" : "Cobrados"}
            </button>
          ))}
        </div>
      </div>

      {vista === "catalogo" && categorias.length > 0 && (
        <div className="pdv-categorias" role="group" aria-label="Categoría">
          <button
            type="button"
            className={categoria === TODAS ? "on" : ""}
            onClick={() => setCategoria(TODAS)}
          >
            Todas
          </button>
          {categorias.map((c) => (
            <button
              key={c.id}
              type="button"
              className={categoria === c.id ? "on" : ""}
              onClick={() => setCategoria(c.id)}
            >
              {c.nombre}
            </button>
          ))}
        </div>
      )}

      {vista === "catalogo" && (
        <ProductosGrid items={visibles} busqueda={busqueda} onProducto={onProducto} />
      )}
      {vista === "mesas" && (
        <MapaMesas
          mesas={mesas}
          abiertas={abiertas}
          onMesa={onMesa}
          onOrdenAbierta={props.onOrdenAbierta}
        />
      )}
      {vista === "cobrados" && (
        <Cobrados ventas={cobrados} onVer={props.onVerCobrado} />
      )}
    </section>
  );
}

function ProductosGrid({
  items,
  busqueda,
  onProducto,
}: {
  items: ItemDeCarta[];
  busqueda: string;
  onProducto: (i: ItemDeCarta) => void;
}) {
  if (!items.length) {
    return (
      <p className="pdv-nada">
        {busqueda
          ? `Nada coincide con “${busqueda}”.`
          : "La carta está vacía: ningún producto tiene precio vigente para esta sucursal."}
      </p>
    );
  }
  return (
    <div className="pdv-grid">
      {items.map((p) => (
        <button
          key={p.producto_comercial_id}
          type="button"
          className="pdv-producto"
          onClick={() => onProducto(p)}
        >
          <span className="pdv-producto-nombre">{p.nombre}</span>
          <span className="pdv-producto-precio">{soles(p.precio_unitario)}</span>
          {p.extras.length > 0 && (
            <span className="pdv-producto-extras">
              {p.extras.length} {p.extras.length === 1 ? "extra" : "extras"}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

function MapaMesas({
  mesas,
  abiertas,
  onMesa,
  onOrdenAbierta,
}: {
  mesas: MesaEnMapa[];
  abiertas: Venta[];
  onMesa: (m: MesaEnMapa) => void;
  onOrdenAbierta: (v: Venta) => void;
}) {
  const ocupadas = mesas.filter((m) => m.venta_id).length;
  return (
    <div className="pdv-mesas">
      {mesas.length > 0 ? (
        <>
          <p className="pdv-mesas-resumen">
            {ocupadas} de {mesas.length} ocupadas
          </p>
          <div className="pdv-mesas-grid">
            {mesas.map((m) => (
              <button
                key={m.id}
                type="button"
                className={`pdv-mesa ${m.venta_id ? "ocupada" : ""}`}
                onClick={() => onMesa(m)}
              >
                <span className="pdv-mesa-num">{m.numero}</span>
                {m.venta_id ? (
                  <>
                    <span className="pdv-mesa-total">{soles(m.total)}</span>
                    <span className="pdv-mesa-info">
                      {m.comensales ? `${m.comensales} pers.` : "en curso"}
                    </span>
                  </>
                ) : (
                  <span className="pdv-mesa-info">Libre</span>
                )}
              </button>
            ))}
          </div>
        </>
      ) : (
        <p className="pdv-nada">
          Esta sucursal no tiene mesas configuradas todavía.
        </p>
      )}

      {abiertas.length > 0 && (
        <>
          <p className="pdv-mesas-resumen">
            {abiertas.length} para llevar/delivery en cocina
          </p>
          <ul className="pdv-abiertas">
            {abiertas.map((v) => (
              <li key={v.id}>
                <button type="button" onClick={() => onOrdenAbierta(v)}>
                  <span className="pdv-cobrado-orden">#{v.numero_orden}</span>
                  <span className="pdv-cobrado-modalidad">
                    {v.modalidad === "delivery" ? "Delivery" : "Para llevar"}
                    {v.referencia_atencion ? ` · ${v.referencia_atencion}` : ""}
                  </span>
                  <strong>{soles(v.total)}</strong>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function Cobrados({
  ventas,
  onVer,
}: {
  ventas: Venta[];
  onVer: (v: Venta) => void;
}) {
  if (!ventas.length) {
    return <p className="pdv-nada">Todavía no hay pedidos cobrados hoy.</p>;
  }
  const total = ventas.reduce((a, v) => a + Number(v.total), 0);
  return (
    <div className="pdv-cobrados">
      <div className="pdv-cobrados-cab">
        <span>
          {ventas.length} {ventas.length === 1 ? "pedido" : "pedidos"}
        </span>
        <strong>{soles(total)}</strong>
      </div>
      <ul>
        {ventas.map((v) => (
          <li key={v.id}>
            <button type="button" onClick={() => onVer(v)}>
              <span className="pdv-cobrado-orden">#{v.numero_orden}</span>
              <span className="pdv-cobrado-modalidad">{v.modalidad}</span>
              <span className="pdv-cobrado-estado">{v.estado}</span>
              <strong>{soles(v.total)}</strong>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
