"use client";

import { useRef } from "react";

import { soles } from "@/lib/pdv";

import {
  descuentoDeBorrador,
  esConsumoPersonal,
  etiquetaMotivoDescuento,
  etiquetaTipo,
  lineasPendientes,
  MOTIVOS_CONSUMO,
  promocionesDeBorrador,
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
  onCerrar: (id: string) => void;
  onLinea: (l: LineaBorrador) => void;
  onAlternarSeleccion: (id: string) => void;
  onLimpiarSeleccion: () => void;
  onMover: () => void;
  onCliente: () => void;
  onTipo: () => void;
  onDescuento: () => void;
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
        onCerrar={props.onCerrar}
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
            onMover={props.onMover}
          />
          <Totales borrador={activo} />
          <Acciones
            borrador={activo}
            onCliente={props.onCliente}
            onTipo={props.onTipo}
            onDescuento={props.onDescuento}
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
  onCerrar,
}: {
  borradores: Borrador[];
  activoId: string | null;
  onActivar: (id: string) => void;
  onNuevo: () => void;
  /** Descarta una pestaña que no llegó a ser un pedido. Un pedido con
   * líneas o ya enviado no se cierra por acá: eso es "Anular pedido", que
   * repone inventario y queda auditado. */
  onCerrar: (id: string) => void;
}) {
  // La última no se cierra: el PDV sin ninguna pestaña no tiene dónde
  // empezar a teclear.
  const cerrables = borradores.length > 1;
  return (
    <div className="pdv-tabs">
      {borradores.map((b) => {
        const total = totalBorrador(b);
        const descartable = cerrables && b.lineas.length === 0 && !b.ventaId;
        return (
          <span key={b.id} className="pdv-tab-envoltura">
            <button
              type="button"
              className="pdv-tab"
              aria-pressed={b.id === activoId}
              onClick={() => onActivar(b.id)}
            >
              {etiquetaTipo(b)}
              {total > 0 && <span className="pdv-tab-monto">{soles(total)}</span>}
            </button>
            {descartable && (
              <button
                type="button"
                className="pdv-tab-cerrar"
                aria-label={`Cerrar ${etiquetaTipo(b)}`}
                title="Descartar este pedido vacío"
                onClick={() => onCerrar(b.id)}
              >
                ×
              </button>
            )}
          </span>
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
  onMover,
}: {
  borrador: Borrador;
  seleccion: Set<string>;
  onLimpiar: () => void;
  onMover: () => void;
}) {
  if (seleccion.size === 0) return null;
  const total = borrador.lineas
    .filter((l) => seleccion.has(l.id))
    .reduce((a, l) => a + totalLinea(l), 0);
  // Mover exige una línea ya enviada a cocina (RN-COM-043): antes de eso el
  // borrador se corrige local, borrando la línea y volviendo a tocar el
  // producto — no hay nada del lado del servidor que reasignar todavía.
  const puedeMover = Boolean(borrador.ventaId) && !esConsumoPersonal(borrador);
  return (
    <div className="pdv-selbar">
      <span>
        {seleccion.size}{" "}
        {seleccion.size === 1 ? "seleccionado" : "seleccionados"}
        {/* En un consumo de personal no hay monto que mostrar: enseñarlo
            contradiría las líneas, que ya salen sin precio. */}
        {esConsumoPersonal(borrador) ? "" : ` · ${soles(total)}`}
      </span>
      <button
        type="button"
        disabled={!puedeMover}
        title={
          puedeMover ? undefined : "Envía el pedido antes de mover productos"
        }
        onClick={onMover}
      >
        Mover productos
      </button>
      <button type="button" onClick={onLimpiar}>
        Quitar selección
      </button>
    </div>
  );
}

function Totales({ borrador }: { borrador: Borrador }) {
  const total = totalBorrador(borrador);
  // El reparto es del pedido, no de lo que se comió: va en su propia fila y
  // no repartido entre las líneas (RN-COM-041). Sin delivery no aparece.
  const reparto = borrador.costoEntrega ?? 0;
  // En su propia fila y no descontado del subtotal: el cliente pregunta
  // cuánto le rebajaron, y un subtotal ya rebajado no responde eso.
  const descuento = descuentoDeBorrador(borrador);
  const promociones = promocionesDeBorrador(borrador);
  return (
    <div className="pdv-totales">
      <div className="pdv-total-fila">
        <span>Subtotal</span>
        <span>{soles(total - reparto + descuento + promociones)}</span>
      </div>
      {/* Cada promoción con su nombre, y no una línea sumada: el cliente
          pregunta cuál se le aplicó, y "promociones: −S/ 40" no lo responde.
          Si el nombre no alcanza para explicarlo, la promoción está mal
          nombrada — pero callarla es peor (ADR-076). */}
      {borrador.promociones.map((p) => (
        <div className="pdv-total-fila" key={p.nombre}>
          <span>{p.nombre}</span>
          <span className="verde">−{soles(p.monto)}</span>
        </div>
      ))}
      {descuento > 0 && (
        <div className="pdv-total-fila">
          <span>
            Descuento
            {borrador.descuento
              ? ` · ${etiquetaMotivoDescuento(borrador.descuento.motivo)}`
              : ""}
          </span>
          <span className="verde">−{soles(descuento)}</span>
        </div>
      )}
      {reparto > 0 && (
        <div className="pdv-total-fila">
          <span>Reparto</span>
          <span>{soles(reparto)}</span>
        </div>
      )}
      <div className="pdv-total-fila grande">
        <span>Total</span>
        <span>{soles(total)}</span>
      </div>
    </div>
  );
}

/** Si al pedido ya le bajaron el total, por cupón o por descuento manual.
 * Fuera del componente para no sumarle ramas a su cuerpo. */
const tieneRebaja = (b: Borrador): boolean => Boolean(b.descuento ?? b.cupon);

function Acciones({
  borrador,
  onCliente,
  onTipo,
  onDescuento,
  onAnular,
  onConsumoPersonal,
}: {
  borrador: Borrador;
  onCliente: () => void;
  onTipo: () => void;
  onDescuento: () => void;
  onAnular: () => void;
  onConsumoPersonal: () => void;
}) {
  const consumo = esConsumoPersonal(borrador);
  const rebajado = tieneRebaja(borrador);
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
      {/* El cupón no pide firma y el descuento manual sí, pero para el
          cajero son la misma pregunta —"¿por qué paga menos?"—, así que es un
          solo botón; la diferencia la hace el diálogo. Un consumo de personal
          ya vale cero: no hay nada que descontar (RN-COM-025). */}
      {!consumo && (
        <button
          type="button"
          className={rebajado ? "puesto" : ""}
          onClick={onDescuento}
        >
          {rebajado ? "Descuento aplicado" : "Descuento / cupón"}
        </button>
      )}
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
  // Lo que espera confirmación. En un pedido ya enviado son el aumento
  // (ADR-075): hasta que alguien toque "Enviar aumento" no hay nada nuevo en
  // cocina, y por eso el botón vuelve a estar vivo en vez de quedarse en
  // "Enviado" para siempre.
  const pendientes = lineasPendientes(activo);
  // Un consumo de personal no se cobra (RN-COM-025): el botón no se
  // deshabilita, desaparece — y "Enviar" pasa a ser la acción principal.
  const consumo = esConsumoPersonal(activo);
  const etiquetaEnvio = !enviado
    ? "Enviar"
    : pendientes.length > 0
      ? `Enviar aumento (${pendientes.length})`
      : "Enviado";
  return (
    <div className="pdv-pago">
      <button
        type="button"
        className={
          consumo || pendientes.length > 0 ? "pdv-boton-pri" : "pdv-boton-sec"
        }
        disabled={ocupado || vacio || pendientes.length === 0}
        onClick={onEnviar}
      >
        {etiquetaEnvio}
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
        {/* Sobre una mesa ya abierta hay líneas que ya están en cocina y
            líneas que todavía no. Sin marcarlo, el mesero no tiene forma de
            saber qué le falta confirmar y termina tocando "Enviar aumento"
            a ciegas — o no tocándolo nunca. */}
        {!linea.enviada && <em className="pdv-linea-pendiente">Sin enviar</em>}
        {linea.nota && <em>{linea.nota}</em>}
        {/* Qué mitades lleva la pizza. Van antes que los extras porque dicen
            QUÉ es el plato, no qué se le agregó — y sin esto dos MitadXMitad
            distintas se ven idénticas en el ticket. */}
        {linea.valores.map((v) => (
          <em key={v.ptavId}>{v.nombre}</em>
        ))}
        {linea.extras.map((e) => (
          <em key={e.productoId}>
            + {e.cantidad > 1 ? `${e.cantidad}× ` : ""}
            {e.nombre}
          </em>
        ))}
        {linea.restas.map((r) => (
          <em key={r.articuloId}>− sin {r.nombre}</em>
        ))}
      </span>
      <span className="pdv-linea-monto">
        {gratis ? "—" : soles(totalLinea(linea))}
      </span>
    </button>
  );
}
