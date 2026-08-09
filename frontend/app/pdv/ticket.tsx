"use client";

import { useRef } from "react";

import { soles } from "@/lib/pdv";

import {
  esConsumoPersonal,
  etiquetaTipo,
  MOTIVOS_CONSUMO,
  totalBorrador,
  totalLinea,
  type Borrador,
  type LineaBorrador,
} from "./tipos";

const etiquetaMotivo = (motivo: string): string =>
  MOTIVOS_CONSUMO.find((m) => m.valor === motivo)?.etiqueta ?? motivo;

type Props = {
  borradores: Borrador[];
  activo: Borrador | null;
  seleccion: Set<string>;
  ocupado: boolean;
  onActivar: (id: string) => void;
  onNuevo: () => void;
  onLinea: (l: LineaBorrador) => void;
  onAlternarSeleccion: (id: string) => void;
  onLimpiarSeleccion: () => void;
  onCliente: () => void;
  onTipo: () => void;
  onAnular: () => void;
  onEnviar: () => void;
  onCobrar: () => void;
  onConsumoPersonal: () => void;
};

/** Panel derecho: el pedido en curso. Es lo único que el cajero mira
 * mientras el cliente habla, así que el total va grande y las acciones
 * peligrosas quedan lejos del pulgar. */
export default function Ticket(props: Props) {
  const { borradores, activo, seleccion } = props;

  return (
    <aside className="pdv-der">
      <Pestanas
        borradores={borradores}
        activoId={activo?.id ?? null}
        onActivar={props.onActivar}
        onNuevo={props.onNuevo}
      />
      {!activo ? (
        <p className="pdv-nada">Sin pedido abierto. Toca + para empezar uno.</p>
      ) : (
        <>
          <Cabecera borrador={activo} />
          <FranjaConsumo borrador={activo} />
          <Lineas
            borrador={activo}
            seleccion={seleccion}
            onLinea={props.onLinea}
            onAlternarSeleccion={props.onAlternarSeleccion}
          />
          <BarraSeleccion
            borrador={activo}
            seleccion={seleccion}
            onLimpiar={props.onLimpiarSeleccion}
          />
          <Totales borrador={activo} />
          <Acciones
            borrador={activo}
            onCliente={props.onCliente}
            onTipo={props.onTipo}
            onAnular={props.onAnular}
            onConsumoPersonal={props.onConsumoPersonal}
          />
          <Pago {...props} activo={activo} />
        </>
      )}
    </aside>
  );
}

function Pestanas({
  borradores,
  activoId,
  onActivar,
  onNuevo,
}: {
  borradores: Borrador[];
  activoId: string | null;
  onActivar: (id: string) => void;
  onNuevo: () => void;
}) {
  return (
    <div className="pdv-tabs">
      {borradores.map((b) => {
        const total = totalBorrador(b);
        return (
          <button
            key={b.id}
            type="button"
            className="pdv-tab"
            aria-pressed={b.id === activoId}
            onClick={() => onActivar(b.id)}
          >
            {etiquetaTipo(b)}
            {total > 0 && <span className="pdv-tab-monto">{soles(total)}</span>}
          </button>
        );
      })}
      <button
        type="button"
        className="pdv-tab-add"
        onClick={onNuevo}
        aria-label="Nuevo pedido"
      >
        +
      </button>
    </div>
  );
}

/** Franja imposible de pasar por alto: el cajero tiene que ver que este
 * pedido no se cobra antes de mandarlo a cocina (RN-COM-025). */
function FranjaConsumo({ borrador }: { borrador: Borrador }) {
  if (!borrador.consumoMotivo) return null;
  return (
    <p className="pdv-consumo-franja" data-testid="franja-consumo">
      Consumo de personal · {etiquetaMotivo(borrador.consumoMotivo)} · sin cobro
    </p>
  );
}

function Cabecera({ borrador }: { borrador: Borrador }) {
  const detalle = [
    borrador.hora,
    borrador.comensales ? `${borrador.comensales} pers.` : null,
    borrador.cliente?.nombre ?? null,
    borrador.ventaId ? "en cocina" : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <header className="pdv-ticket-cab">
      <h2>
        {borrador.numeroOrden ? `#${borrador.numeroOrden} · ` : ""}
        {etiquetaTipo(borrador)}
      </h2>
      <p>{detalle}</p>
    </header>
  );
}

function Lineas({
  borrador,
  seleccion,
  onLinea,
  onAlternarSeleccion,
}: {
  borrador: Borrador;
  seleccion: Set<string>;
  onLinea: (l: LineaBorrador) => void;
  onAlternarSeleccion: (id: string) => void;
}) {
  if (borrador.lineas.length === 0) {
    return (
      <div className="pdv-lineas">
        <p className="pdv-vacio-ticket">
          Toca un producto del catálogo
          <br />
          para comenzar el pedido
        </p>
      </div>
    );
  }
  return (
    <div className="pdv-lineas">
      {borrador.lineas.map((l) => (
        <Linea
          key={l.id}
          linea={l}
          gratis={esConsumoPersonal(borrador)}
          seleccionada={seleccion.has(l.id)}
          modoSeleccion={seleccion.size > 0}
          onClick={() =>
            seleccion.size > 0 ? onAlternarSeleccion(l.id) : onLinea(l)
          }
          onLargo={() => onAlternarSeleccion(l.id)}
        />
      ))}
    </div>
  );
}

function BarraSeleccion({
  borrador,
  seleccion,
  onLimpiar,
}: {
  borrador: Borrador;
  seleccion: Set<string>;
  onLimpiar: () => void;
}) {
  if (seleccion.size === 0) return null;
  const total = borrador.lineas
    .filter((l) => seleccion.has(l.id))
    .reduce((a, l) => a + totalLinea(l), 0);
  return (
    <div className="pdv-selbar">
      <span>
        {seleccion.size}{" "}
        {seleccion.size === 1 ? "seleccionado" : "seleccionados"}
        {/* En un consumo de personal no hay monto que mostrar: enseñarlo
            contradiría las líneas, que ya salen sin precio. */}
        {esConsumoPersonal(borrador) ? "" : ` · ${soles(total)}`}
      </span>
      <button type="button" onClick={onLimpiar}>
        Quitar selección
      </button>
    </div>
  );
}

function Totales({ borrador }: { borrador: Borrador }) {
  const total = totalBorrador(borrador);
  return (
    <div className="pdv-totales">
      <div className="pdv-total-fila">
        <span>Subtotal</span>
        <span>{soles(total)}</span>
      </div>
      <div className="pdv-total-fila grande">
        <span>Total</span>
        <span>{soles(total)}</span>
      </div>
    </div>
  );
}

function Acciones({
  borrador,
  onCliente,
  onTipo,
  onAnular,
  onConsumoPersonal,
}: {
  borrador: Borrador;
  onCliente: () => void;
  onTipo: () => void;
  onAnular: () => void;
  onConsumoPersonal: () => void;
}) {
  const consumo = esConsumoPersonal(borrador);
  return (
    <div className="pdv-acciones">
      <button
        type="button"
        className={borrador.cliente ? "puesto" : ""}
        onClick={onCliente}
      >
        {borrador.cliente ? borrador.cliente.nombre.split(" ")[0] : "Cliente"}
      </button>
      <button
        type="button"
        className={consumo ? "puesto" : ""}
        // Ya enviado no se cambia: el pedido salió a cocina con su tipo y el
        // insumo ya se descontó como lo que fuera.
        disabled={Boolean(borrador.ventaId)}
        onClick={onConsumoPersonal}
      >
        {consumo ? "Quitar consumo" : "Consumo de personal"}
      </button>
      <button
        type="button"
        className={borrador.tipo ? "puesto" : ""}
        onClick={onTipo}
      >
        {borrador.tipo ? etiquetaTipo(borrador) : "Tipo de orden"}
      </button>
      <button
        type="button"
        className="riesgo"
        disabled={borrador.lineas.length === 0}
        onClick={onAnular}
      >
        Anular pedido
      </button>
    </div>
  );
}

function Pago({
  activo,
  seleccion,
  ocupado,
  onEnviar,
  onCobrar,
}: Props & { activo: Borrador }) {
  const enviado = Boolean(activo.ventaId);
  const vacio = activo.lineas.length === 0;
  // Un consumo de personal no se cobra (RN-COM-025): el botón no se
  // deshabilita, desaparece — y "Enviar" pasa a ser la acción principal.
  const consumo = esConsumoPersonal(activo);
  return (
    <div className="pdv-pago">
      <button
        type="button"
        className={consumo ? "pdv-boton-pri" : "pdv-boton-sec"}
        disabled={ocupado || enviado || vacio}
        onClick={onEnviar}
      >
        {enviado ? "Enviado" : "Enviar"}
      </button>
      {!consumo && (
        <button
          type="button"
          className="pdv-boton-pri"
          disabled={ocupado || vacio}
          onClick={onCobrar}
        >
          {seleccion.size > 0 ? `Cobrar ${seleccion.size}` : "Cobrar"}
        </button>
      )}
    </div>
  );
}

/** Mantener presionado entra a modo selección; el toque corto abre la
 * configuración de la línea. Sin esto, elegir qué cobrar exigiría un modo
 * aparte que el cajero tendría que acordarse de activar. */
function Linea({
  linea,
  gratis,
  seleccionada,
  modoSeleccion,
  onClick,
  onLargo,
}: {
  linea: LineaBorrador;
  gratis: boolean;
  seleccionada: boolean;
  modoSeleccion: boolean;
  onClick: () => void;
  onLargo: () => void;
}) {
  // Refs, no state local: seleccionar dispara un re-render del padre a
  // mitad de la pulsación (cambia `seleccion`), y una variable de closure
  // se reiniciaría con ese render — el click que sigue al soltar volvería
  // a alternar la selección que el propio largo acaba de fijar.
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);
  const disparado = useRef(false);

  return (
    <button
      type="button"
      className={`pdv-linea ${seleccionada ? "sel" : ""}`}
      onPointerDown={() => {
        disparado.current = false;
        temporizador.current = setTimeout(() => {
          disparado.current = true;
          onLargo();
        }, 420);
      }}
      onPointerUp={() => temporizador.current && clearTimeout(temporizador.current)}
      onPointerLeave={() => temporizador.current && clearTimeout(temporizador.current)}
      onContextMenu={(e) => {
        e.preventDefault();
        onLargo();
      }}
      onClick={() => {
        if (!disparado.current) onClick();
      }}
      aria-pressed={modoSeleccion ? seleccionada : undefined}
    >
      <span className="pdv-linea-cant">{linea.cantidad}</span>
      <span className="pdv-linea-nombre">
        {linea.nombre}
        {linea.nota && <em>{linea.nota}</em>}
        {linea.extras.map((e) => (
          <em key={e.productoId}>
            + {e.cantidad > 1 ? `${e.cantidad}× ` : ""}
            {e.nombre}
          </em>
        ))}
      </span>
      <span className="pdv-linea-monto">
        {gratis ? "—" : soles(totalLinea(linea))}
      </span>
    </button>
  );
}
