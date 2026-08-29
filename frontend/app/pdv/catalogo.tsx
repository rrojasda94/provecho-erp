"use client";

import { Printer } from "lucide-react";
import { useMemo, useState } from "react";

import type { Falla, Lista } from "@/lib/carga";
import { soles, type ItemDeCarta, type MesaEnMapa, type Venta } from "@/lib/pdv";

type Vista = "catalogo" | "mesas" | "abiertas" | "cobrados";
const TODAS = "__todas__";

const ETIQUETA_VISTA: Record<Vista, string> = {
  catalogo: "Catálogo",
  mesas: "Mesas",
  abiertas: "Cuentas",
  cobrados: "Cobrados",
};

type Props = {
  carta: ItemDeCarta[];
  mesas: Lista<MesaEnMapa>;
  cobrados: Lista<Venta>;
  abiertas: Lista<Venta>;
  /** La carta no se pide hasta que hay caja abierta, así que "vacía" antes
   * de eso no significa lo mismo. Sin esta distinción el PDV culpaba a la
   * lista de precios de algo que solo era el turno sin abrir. */
  cajaAbierta: boolean;
  vista: Vista;
  onVista: (v: Vista) => void;
  onProducto: (item: ItemDeCarta) => void;
  onMesa: (mesa: MesaEnMapa) => void;
  onOrdenAbierta: (venta: Venta) => void;
  onVerCobrado: (venta: Venta) => void;
  /** Reimprime la comanda de una cuenta abierta. Cuenta como reimpresión —
   * es el mismo endpoint que usa cocina— y por eso el botón está separado
   * de la fila: tocarlo al querer abrir el pedido sacaría papel de más. */
  onImprimirComanda: (venta: Venta) => void;
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
          {(["catalogo", "mesas", "abiertas", "cobrados"] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={vista === v}
              onClick={() => onVista(v)}
            >
              {ETIQUETA_VISTA[v]}
              {v === "abiertas" && abiertas.datos.length > 0
                ? ` (${abiertas.datos.length})`
                : ""}
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
        <ProductosGrid
          items={visibles}
          busqueda={busqueda}
          cajaAbierta={props.cajaAbierta}
          onProducto={onProducto}
        />
      )}
      {vista === "mesas" && (
        <MapaMesas
          mesas={mesas}
          abiertas={abiertas}
          onMesa={onMesa}
          onOrdenAbierta={props.onOrdenAbierta}
        />
      )}
      {vista === "abiertas" && (
        <Abiertas
          ventas={abiertas}
          onVer={props.onOrdenAbierta}
          onImprimir={props.onImprimirComanda}
        />
      )}
      {vista === "cobrados" && (
        <Cobrados ventas={cobrados} onVer={props.onVerCobrado} />
      )}
    </section>
  );
}

/** Cuántos extras ofrece la tarjeta. Con presentaciones los extras cuelgan
 * de cada una, así que se cuenta la más surtida: sumarlas diría "18 extras"
 * por seis sabores repetidos en tres tamaños. */
function cuantosExtras(p: ItemDeCarta): number {
  if (p.variantes.length === 0) return p.extras.length;
  return Math.max(...p.variantes.map((v) => v.extras.length), 0);
}

/** RN-INV-013: si el producto o alguna de sus presentaciones usa un insumo
 * con poco stock, avisa — nunca deja de mostrarse ni de venderse. */
function tieneStockBajo(p: ItemDeCarta): boolean {
  return p.stock_bajo || p.variantes.some((v) => v.stock_bajo);
}

function ProductosGrid({
  items,
  busqueda,
  cajaAbierta,
  onProducto,
}: {
  items: ItemDeCarta[];
  busqueda: string;
  cajaAbierta: boolean;
  onProducto: (i: ItemDeCarta) => void;
}) {
  if (!items.length) {
    return (
      <p className="pdv-nada">
        {busqueda
          ? `Nada coincide con “${busqueda}”.`
          : cajaAbierta
            ? "La carta está vacía: ningún producto tiene precio vigente para esta sucursal."
            : "Abre la caja para ver la carta."}
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
          <span className="pdv-producto-nombre">
            {p.nombre}
            {tieneStockBajo(p) && (
              <span
                className="pdv-producto-stock-bajo"
                title="Insumo con poco stock — la venta no se bloquea"
              >
                ⚠
              </span>
            )}
          </span>
          <span className="pdv-producto-precio">
            {/* Con variantes el precio de la tarjeta es el "desde": el que
                se cobra sale del tamaño que se elija. */}
            {p.variantes.length > 0 ? "desde " : ""}
            {soles(p.precio_unitario)}
          </span>
          {(p.variantes.length > 0 || cuantosExtras(p) > 0) && (
            <span className="pdv-producto-extras">
              {[
                p.variantes.length > 0 ? `${p.variantes.length} presentaciones` : "",
                cuantosExtras(p) > 0
                  ? `${cuantosExtras(p)} ${cuantosExtras(p) === 1 ? "extra" : "extras"}`
                  : "",
              ]
                .filter(Boolean)
                .join(" · ")}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

/**
 * Lo que se muestra cuando una lista no se pudo traer.
 *
 * Un fetch caído no es un día sin ventas: dibujarlo como lista vacía fue lo
 * que dejó indiagnosticable, desde la pantalla, una venta que sí estaba en
 * la base. Por eso se dice qué falló, se deja el detalle técnico a la vista
 * y se ofrece reintentar sin recargar la página — recargar el PDV significa
 * perder los borradores abiertos en las pestañas del ticket.
 */
function Fallo({ falla, onReintentar }: { falla: Falla; onReintentar: () => void }) {
  return (
    <div className="pdv-fallo" role="alert">
      <strong>{falla.mensaje}</strong>
      <span>
        {falla.status ? `Error ${falla.status}` : "Sin respuesta del servidor"}
        {falla.detalle ? ` · ${falla.detalle}` : ""}
      </span>
      <button type="button" className="pdv-boton-sec" onClick={onReintentar}>
        Reintentar
      </button>
    </div>
  );
}

function MapaMesas({
  mesas,
  abiertas,
  onMesa,
  onOrdenAbierta,
}: {
  mesas: Lista<MesaEnMapa>;
  abiertas: Lista<Venta>;
  onMesa: (m: MesaEnMapa) => void;
  onOrdenAbierta: (v: Venta) => void;
}) {
  const ocupadas = mesas.datos.filter((m) => m.venta_id).length;
  return (
    <div className="pdv-mesas">
      {mesas.falla ? (
        <Fallo falla={mesas.falla} onReintentar={mesas.recargar} />
      ) : mesas.datos.length > 0 ? (
        <>
          <p className="pdv-mesas-resumen">
            {ocupadas} de {mesas.datos.length} ocupadas
          </p>
          <div className="pdv-mesas-grid">
            {mesas.datos.map((m) => (
              <button
                key={m.id}
                type="button"
                className={`pdv-mesa ${m.venta_id ? "ocupada" : ""}`}
                style={{ gridColumn: m.pos_x + 1, gridRow: m.pos_y + 1 }}
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
          Esta sucursal no tiene mesas configuradas todavía. Se configuran
          en Ventas → Mesas.
        </p>
      )}

      {abiertas.falla && (
        <Fallo falla={abiertas.falla} onReintentar={abiertas.recargar} />
      )}

      {!abiertas.falla && abiertas.datos.length > 0 && (
        <>
          <p className="pdv-mesas-resumen">
            {abiertas.datos.length} para llevar/delivery en cocina
          </p>
          <ul className="pdv-abiertas">
            {abiertas.datos.map((v) => (
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

/** Todo lo enviado a cocina y sin cobrar: mesa, para llevar y delivery en la
 * misma lista.
 *
 * Existía como una nota al pie del mapa de mesas —y filtrando fuera las de
 * mesa—, así que un pedido para llevar solo se encontraba entrando a Mesas y
 * bajando, y uno de mesa había que reconocerlo por el color de la mesa. Lo
 * que la caja pregunta es "¿qué falta cobrar?", y eso no es una pregunta
 * sobre el salón. */
function Abiertas({
  ventas,
  onVer,
  onImprimir,
}: {
  ventas: Lista<Venta>;
  onVer: (v: Venta) => void;
  onImprimir: (v: Venta) => void;
}) {
  if (ventas.falla) {
    return (
      <div className="pdv-cobrados">
        <Fallo falla={ventas.falla} onReintentar={ventas.recargar} />
      </div>
    );
  }
  if (!ventas.datos.length) {
    return <p className="pdv-nada">No hay cuentas abiertas: todo lo enviado está cobrado.</p>;
  }
  const total = ventas.datos.reduce((a, v) => a + Number(v.total), 0);
  return (
    <div className="pdv-cobrados">
      <div className="pdv-cobrados-cab">
        <span>
          {ventas.datos.length} sin cobrar
        </span>
        <strong>{soles(total)}</strong>
      </div>
      <ul>
        {ventas.datos.map((v) => (
          <li key={v.id} className="pdv-abierta-fila">
            <button type="button" onClick={() => onVer(v)}>
              <span className="pdv-cobrado-orden">#{v.numero_orden}</span>
              <span className="pdv-cobrado-modalidad">
                {v.mesa_id ? "Mesa" : v.modalidad === "delivery" ? "Delivery" : "Para llevar"}
                {v.referencia_atencion ? ` · ${v.referencia_atencion}` : ""}
              </span>
              <strong>{soles(v.total)}</strong>
            </button>
            <button
              type="button"
              className="pdv-abierta-imprimir"
              title="Reimprimir comanda"
              aria-label={`Reimprimir comanda del pedido ${v.numero_orden}`}
              onClick={() => onImprimir(v)}
            >
              <Printer aria-hidden size={18} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Cobrados({
  ventas,
  onVer,
}: {
  ventas: Lista<Venta>;
  onVer: (v: Venta) => void;
}) {
  // El vacío queda reservado para la respuesta exitosa sin filas: si la
  // petición se cayó, "todavía no hay pedidos cobrados" sería mentira, y es
  // exactamente la mentira que hay que poder descartar cuando un cobro no
  // aparece acá.
  if (ventas.falla) {
    return (
      <div className="pdv-cobrados">
        <Fallo falla={ventas.falla} onReintentar={ventas.recargar} />
      </div>
    );
  }
  if (!ventas.datos.length) {
    return <p className="pdv-nada">Todavía no hay pedidos cobrados hoy.</p>;
  }
  const total = ventas.datos.reduce((a, v) => a + Number(v.total), 0);
  return (
    <div className="pdv-cobrados">
      <div className="pdv-cobrados-cab">
        <span>
          {ventas.datos.length} {ventas.datos.length === 1 ? "pedido" : "pedidos"}
        </span>
        <strong>{soles(total)}</strong>
      </div>
      <ul>
        {ventas.datos.map((v) => (
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
