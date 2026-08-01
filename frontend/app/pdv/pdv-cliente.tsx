"use client";

import { useCallback, useEffect, useState } from "react";

import {
  api,
  claveIdempotencia,
  ErrorApi,
  soles,
  type ClienteBuscado,
  type ItemDeCarta,
  type MesaEnMapa,
} from "@/lib/pdv";

import Catalogo from "./catalogo";
import {
  DialogoApertura,
  DialogoCliente,
  DialogoCobro,
  DialogoProducto,
  DialogoTipo,
} from "./dialogos";
import Ticket from "./ticket";
import {
  faltaEnBorrador,
  totalBorrador,
  totalLinea,
  type Borrador,
  type LineaBorrador,
} from "./tipos";
import { useDatosPdv } from "./use-datos-pdv";

type Props = {
  empresaId: string | null;
  sucursalId: string;
  puntoVenta: {
    id: string;
    serieBoleta: string;
    serieFactura: string;
    modalidades: string[];
  };
};

const hora = () =>
  new Date().toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" });

function nuevoBorrador(mesa?: MesaEnMapa): Borrador {
  return {
    id: crypto.randomUUID(),
    tipo: mesa ? "mesa" : null,
    mesaId: mesa?.id ?? null,
    mesaNumero: mesa?.numero ?? null,
    comensales: null,
    direccion: null,
    cliente: null,
    lineas: [],
    ventaId: null,
    numeroOrden: null,
    hora: hora(),
  };
}

export default function PdvCliente({ empresaId, sucursalId, puntoVenta }: Props) {
  const datos = useDatosPdv(empresaId, puntoVenta.id, sucursalId);
  const [borradores, setBorradores] = useState<Borrador[]>([nuevoBorrador()]);
  const [activoId, setActivoId] = useState<string | null>(null);
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set());
  const [vista, setVista] = useState<"catalogo" | "mesas" | "cobrados">("catalogo");
  const [dialogo, setDialogo] = useState<"cliente" | "tipo" | "cobro" | null>(null);
  const [lineaEnEdicion, setLineaEnEdicion] = useState<LineaBorrador | null>(null);
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const activo = borradores.find((b) => b.id === activoId) ?? borradores[0] ?? null;

  const notificar = useCallback((texto: string) => {
    setAviso(texto);
    setTimeout(() => setAviso(""), 3500);
  }, []);

  const parchar = useCallback(
    (cambios: Partial<Borrador>) => {
      if (!activo) return;
      setBorradores((bs) =>
        bs.map((b) => (b.id === activo.id ? { ...b, ...cambios } : b)),
      );
    },
    [activo],
  );

  useEffect(() => {
    if (!activoId && borradores[0]) setActivoId(borradores[0].id);
  }, [activoId, borradores]);

  // El precio depende de la modalidad: al cambiar el tipo de orden hay que
  // recotizar la carta (RN-PRC-003).
  useEffect(() => {
    if (activo?.tipo) datos.setModalidad(activo.tipo);
  }, [activo?.tipo, datos]);

  const abrirNuevo = (mesa?: MesaEnMapa) => {
    const b = nuevoBorrador(mesa);
    setBorradores((bs) => [...bs, b]);
    setActivoId(b.id);
    return b;
  };

  const cerrarPedido = (id: string) => {
    setBorradores((bs) => {
      const resto = bs.filter((b) => b.id !== id);
      const siguiente = resto.length ? resto : [nuevoBorrador()];
      setActivoId(siguiente[0].id);
      return siguiente;
    });
    setSeleccion(new Set());
  };

  const agregarProducto = (item: ItemDeCarta) => {
    if (!activo) return;
    if (activo.ventaId) {
      notificar("Este pedido ya se envió. Usa + para abrir uno nuevo.");
      return;
    }
    const existente = activo.lineas.find(
      (l) =>
        l.productoId === item.producto_comercial_id && !l.nota && !l.extras.length,
    );
    parchar({
      lineas: existente
        ? activo.lineas.map((l) =>
            l.id === existente.id ? { ...l, cantidad: l.cantidad + 1 } : l,
          )
        : [...activo.lineas, lineaDesde(item)],
    });
  };

  const cuerpoVenta = (b: Borrador) => ({
    sucursal_id: sucursalId,
    punto_venta_id: puntoVenta.id,
    canal: "pdv",
    modalidad: b.tipo,
    idempotency_key: claveIdempotencia("venta"),
    cliente_id: b.cliente?.id ?? null,
    mesa_id: b.mesaId,
    comensales: b.comensales,
    referencia_atencion: b.tipo === "mesa" ? null : (b.cliente?.nombre ?? null),
    items: b.lineas.map((l) => ({
      producto_comercial_id: l.productoId,
      cantidad: String(l.cantidad),
      grupo_cobro: l.grupoCobro,
      extras: l.extras.map((e) => ({
        producto_comercial_id: e.productoId,
        cantidad: String(e.cantidad),
      })),
    })),
  });

  /** Puerta común de Enviar y Cobrar: cobrar es enviar + cobrar, así que
   * exigen lo mismo (RN-COM-005). */
  const revisarAntesDeSalir = (b: Borrador, verbo: string): boolean => {
    const falta = faltaEnBorrador(b);
    if (!falta) return true;
    notificar(`${falta} antes de ${verbo}`);
    setDialogo("tipo");
    return false;
  };

  const enviar = async () => {
    if (!activo || !revisarAntesDeSalir(activo, "enviar")) return;
    setOcupado(true);
    try {
      const venta = await api.crearVenta(cuerpoVenta(activo));
      parchar({ ventaId: venta.id, numeroOrden: venta.numero_orden });
      setSeleccion(new Set());
      notificar(`Orden #${venta.numero_orden} enviada a cocina`);
      datos.recargarMesas();
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo enviar el pedido"));
    } finally {
      setOcupado(false);
    }
  };

  const confirmarCobro = async (
    pagos: Array<{ medioId: string; monto: number }>,
    doc: string,
    nombre: string,
  ) => {
    if (!activo) return;
    setOcupado(true);
    try {
      const { ventaId, numero } = await asegurarVenta(activo);
      await registrarPagos(ventaId, pagos, doc, nombre);
      notificar(
        `Orden #${numero} cobrada · ${soles(totalBorrador(activo))} · ${
          doc.length === 11 ? "factura" : "boleta"
        } emitida`,
      );
      setDialogo(null);
      cerrarPedido(activo.id);
      datos.recargarMesas();
      datos.recargarCobrados();
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo completar el cobro"));
    } finally {
      setOcupado(false);
    }
  };

  /** Si el pedido nunca pasó por cocina, la venta nace en el cobro. */
  const asegurarVenta = async (b: Borrador) => {
    if (b.ventaId) return { ventaId: b.ventaId, numero: b.numeroOrden };
    const venta = await api.crearVenta(cuerpoVenta(b));
    return { ventaId: venta.id, numero: venta.numero_orden };
  };

  const abrirCaja = async (
    monto: number,
    detalle: Record<string, number>,
    encargado: { username: string; pin: string },
  ) => {
    setOcupado(true);
    try {
      // El PIN del encargado sirve para dos cosas a la vez: verifica que
      // realmente es él y devuelve su id, que es el `relevo_encargado_id`
      // de la cadena de custodia (RN-MDP-002).
      const elevacion = await api.autorizar(
        encargado.username,
        encargado.pin,
        "accounting.caja_operar",
      );
      datos.setCaja(
        await api.abrirCaja({
          punto_venta_id: puntoVenta.id,
          relevo_encargado_id: elevacion.autorizado_por,
          monto_apertura: String(monto),
          detalle_denominaciones: detalle,
        }),
      );
      notificar(`Caja abierta con ${soles(monto)}`);
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo abrir la caja"));
    } finally {
      setOcupado(false);
    }
  };

  const elegirMesa = (mesa: MesaEnMapa) => {
    if (mesa.venta_id) {
      notificar(
        `Mesa ${mesa.numero} tiene la orden #${mesa.numero_orden} abierta por ${soles(mesa.total)}`,
      );
      return;
    }
    abrirNuevo(mesa);
    setVista("catalogo");
  };

  const crearCliente = async (nombre: string, telefono: string) => {
    try {
      await api.crearCliente({ nombre, telefono });
      const [encontrado] = await api.buscarClientes(telefono);
      if (encontrado) {
        parchar({ cliente: encontrado, direccion: encontrado.direccion });
        notificar(`${encontrado.nombre} guardado y asignado`);
      }
      setDialogo(null);
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo crear el cliente"));
    }
  };

  if (!datos.cajaResuelta) {
    return <main className="pdv-vacio">Cargando el punto de venta…</main>;
  }

  return (
    <main className="pdv">
      <header className="pdv-top">
        <div className="pdv-marca">
          <strong>Punto de venta</strong>
          <small>Serie {puntoVenta.serieBoleta}</small>
        </div>
        <span className={`pdv-pill ${datos.caja ? "ok" : "off"}`}>
          {datos.caja ? "Caja abierta" : "Caja cerrada"}
        </span>
        <span className="pdv-spacer" />
        <span className="pdv-meta">{hora()}</span>
      </header>

      <div className="pdv-shell">
        <Catalogo
          carta={datos.carta}
          mesas={datos.mesas}
          cobrados={datos.cobrados}
          vista={vista}
          onVista={setVista}
          onProducto={agregarProducto}
          onMesa={elegirMesa}
        />
        <Ticket
          borradores={borradores}
          activo={activo}
          seleccion={seleccion}
          ocupado={ocupado || !datos.caja}
          onActivar={setActivoId}
          onNuevo={() => abrirNuevo()}
          onLinea={setLineaEnEdicion}
          onAlternarSeleccion={(id) => setSeleccion(alternar(seleccion, id))}
          onLimpiarSeleccion={() => setSeleccion(new Set())}
          onCliente={() => setDialogo("cliente")}
          onTipo={() => setDialogo("tipo")}
          onMas={() => notificar("Más opciones: pendiente en esta versión")}
          onEnviar={enviar}
          onCobrar={() => {
            if (activo && revisarAntesDeSalir(activo, "cobrar")) setDialogo("cobro");
          }}
        />
      </div>

      {aviso && <p className="pdv-aviso">{aviso}</p>}

      <DialogoApertura
        abierto={!datos.caja}
        onAbrir={abrirCaja}
        ocupado={ocupado}
      />
      <DialogoProducto
        linea={lineaEnEdicion}
        item={
          datos.carta.find(
            (c) => c.producto_comercial_id === lineaEnEdicion?.productoId,
          ) ?? null
        }
        onCerrar={() => setLineaEnEdicion(null)}
        onGuardar={(l) => {
          parchar({
            lineas: activo?.lineas.map((x) => (x.id === l.id ? l : x)) ?? [],
          });
          setLineaEnEdicion(null);
        }}
        onQuitar={(id) => {
          parchar({ lineas: activo?.lineas.filter((x) => x.id !== id) ?? [] });
          setLineaEnEdicion(null);
        }}
      />
      <DialogoTipo
        abierto={dialogo === "tipo"}
        borrador={activo}
        mesas={datos.mesas}
        onCerrar={() => setDialogo(null)}
        onConfirmar={(cambios) => {
          parchar(cambios);
          setDialogo(null);
        }}
      />
      <DialogoCliente
        abierto={dialogo === "cliente"}
        onCerrar={() => setDialogo(null)}
        onBuscar={api.buscarClientes}
        onElegir={(c: ClienteBuscado) => {
          parchar({ cliente: c, direccion: c.direccion });
          setDialogo(null);
        }}
        onCrear={crearCliente}
      />
      <DialogoCobro
        abierto={dialogo === "cobro"}
        total={totalACobrar(activo, seleccion)}
        medios={datos.medios}
        ocupado={ocupado}
        onCerrar={() => setDialogo(null)}
        onConfirmar={confirmarCobro}
      />
    </main>
  );
}

/** El receptor viaja con el pago que cierra la cuenta: es ese el que
 * dispara la emisión del comprobante. */
async function registrarPagos(
  ventaId: string,
  pagos: Array<{ medioId: string; monto: number }>,
  doc: string,
  nombre: string,
) {
  for (const [i, p] of pagos.entries()) {
    const ultimo = i === pagos.length - 1;
    await api.registrarPago(ventaId, {
      medio_pago_id: p.medioId,
      monto: String(p.monto),
      idempotency_key: claveIdempotencia("pago"),
      grupo_cobro: 1,
      receptor_num_doc: ultimo ? doc || null : null,
      receptor_nombre: ultimo ? nombre || null : null,
    });
  }
}

function lineaDesde(item: ItemDeCarta): LineaBorrador {
  return {
    id: crypto.randomUUID(),
    productoId: item.producto_comercial_id,
    nombre: item.nombre,
    precio: Number(item.precio_unitario),
    cantidad: 1,
    nota: "",
    extras: [],
    grupoCobro: 1,
  };
}

function alternar(seleccion: Set<string>, id: string): Set<string> {
  const s = new Set(seleccion);
  if (s.has(id)) s.delete(id);
  else s.add(id);
  return s;
}

/** Sin selección se cobra todo; con selección, solo lo elegido. */
function totalACobrar(activo: Borrador | null, seleccion: Set<string>): number {
  if (!activo) return 0;
  if (seleccion.size === 0) return totalBorrador(activo);
  return activo.lineas
    .filter((l) => seleccion.has(l.id))
    .reduce((a, l) => a + totalLinea(l), 0);
}

function mensajeDe(e: unknown, porDefecto: string): string {
  return e instanceof ErrorApi ? e.message : porDefecto;
}
