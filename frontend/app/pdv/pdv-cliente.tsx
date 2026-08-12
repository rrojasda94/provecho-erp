"use client";

import { useCallback, useEffect, useState } from "react";

import { esSinPermiso, type Falla } from "@/lib/carga";
import {
  api,
  claveIdempotencia,
  ErrorApi,
  soles,
  type CajaAbierta,
  type ClienteBuscado,
  type ItemDeCarta,
  type MesaEnMapa,
  type Venta,
  type VentaItem,
  type VentaNueva,
} from "@/lib/pdv";

import Catalogo from "./catalogo";
import {
  DialogoApertura,
  DialogoCierre,
  DialogoCliente,
  DialogoCobro,
  DialogoConsumoPersonal,
  Dialogo,
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
import { useCajaPdv } from "./use-caja-pdv";
import { useDatosPdv } from "./use-datos-pdv";

type Props = {
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
    consumoMotivo: null,
    consumoAutorizacion: null,
  };
}

function EstadoCaja({
  caja,
  onClick,
}: {
  caja: CajaAbierta | null;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`pdv-pill ${caja ? "ok" : "off"}`}
      data-testid="estado-caja"
      disabled={!caja}
      onClick={onClick}
    >
      {caja ? "Caja abierta · cerrar" : "Caja cerrada"}
    </button>
  );
}

function tituloComprobante(venta: Venta | null): string {
  return venta ? `Orden #${venta.numero_orden}` : "Comprobante";
}

/** Qué mostrar en lugar del PDV mientras no se sabe si hay caja abierta, o
 * `null` para dejar pasar.
 *
 * Que no se pueda **preguntar** por la caja no es lo mismo que no haberla:
 * ofrecer la apertura ahí lleva a pedir la de una caja que quizá ya está
 * abierta, que el servidor rechaza por duplicada, y el cajero queda sin poder
 * vender ni entender por qué. */
function bloqueoDeCaja(resuelta: boolean, falla: Falla | null) {
  if (!resuelta) return <main className="pdv-vacio">Cargando el punto de venta…</main>;
  if (!falla) return null;
  const detalle = esSinPermiso(falla)
    ? "Tu usuario no puede consultar la caja de esta sucursal. Pídele a un administrador el permiso `accounting.caja_operar`."
    : "No se pudo consultar el estado de la caja. Reintenta en unos segundos; si sigue, avisa a soporte.";
  return (
    <main className="pdv-vacio">
      <h1>{falla.mensaje}</h1>
      <p>{detalle}</p>
    </main>
  );
}

export default function PdvCliente({ sucursalId, puntoVenta }: Props) {
  const datos = useDatosPdv(puntoVenta.id, sucursalId);
  const [borradores, setBorradores] = useState<Borrador[]>([nuevoBorrador()]);
  const [activoId, setActivoId] = useState<string | null>(null);
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set());
  const [vista, setVista] = useState<"catalogo" | "mesas" | "cobrados">("catalogo");
  const [dialogo, setDialogo] = useState<
    "cliente" | "tipo" | "cobro" | "cierre" | "consumo" | null
  >(null);
  const [lineaEnEdicion, setLineaEnEdicion] = useState<LineaBorrador | null>(null);
  const [cobradoAVer, setCobradoAVer] = useState<Venta | null>(null);
  const [precuentaAVer, setPrecuentaAVer] = useState("");
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const activo = borradores.find((b) => b.id === activoId) ?? borradores[0] ?? null;

  const { abrirCaja, cerrarCaja, posDelTurno } = useCajaPdv({
    puntoVentaId: puntoVenta.id,
    caja: datos.caja,
    setCaja: datos.setCaja,
    setOcupado,
    notificar: (texto) => notificar(texto),
    mensajeDe,
    alCerrarTurno: () => setDialogo(null),
  });

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

  /** Cada toque abre el diálogo de personalización (cantidad, nota, extras)
   * antes de que la línea exista: agregar a ciegas fuerza a corregir
   * después tocando la línea, que es el mismo trabajo pero en dos pasos. */
  const agregarProducto = (item: ItemDeCarta) => {
    if (!activo) return;
    if (activo.ventaId) {
      notificar("Este pedido ya se envió. Usa + para abrir uno nuevo.");
      return;
    }
    setLineaEnEdicion(lineaDesde(item));
  };

  /** `modalidad` es obligatoria en el contrato y `b.tipo` puede ser null
   * mientras el borrador se arma. `revisarAntesDeSalir` ya lo impide antes
   * de enviar o cobrar (RN-COM-005); esto lo hace explícito para el tipo,
   * porque un `null` acá es un 422 en medio de un cobro. */
  const cuerpoVenta = (b: Borrador): VentaNueva => {
    if (!b.tipo) throw new Error("El pedido no tiene tipo de orden");
    return {
      sucursal_id: sucursalId,
      punto_venta_id: puntoVenta.id,
      canal: "pdv",
      modalidad: b.tipo,
      idempotency_key: claveIdempotencia("venta"),
      cliente_id: b.cliente?.id ?? null,
      mesa_id: b.mesaId,
      comensales: b.comensales,
      referencia_atencion: b.tipo === "mesa" ? null : (b.cliente?.nombre ?? null),
      // Comida del personal: el servidor pone los precios en cero y exige la
      // elevación del encargado (RN-COM-025).
      ...(b.consumoMotivo
        ? {
            tipo: "consumo_personal",
            consumo_motivo: b.consumoMotivo,
            autorizacion: b.consumoAutorizacion ?? undefined,
          }
        : {}),
      items: b.lineas.map((l) => ({
        producto_comercial_id: l.productoId,
        cantidad: String(l.cantidad),
        grupo_cobro: l.grupoCobro,
        extras: l.extras.map((e) => ({
          producto_comercial_id: e.productoId,
          cantidad: String(e.cantidad),
        })),
        sin_articulo_ids: l.restas.map((r) => r.articuloId),
      })),
    };
  };

  /** Puerta común de Enviar y Cobrar: cobrar es enviar + cobrar, así que
   * exigen lo mismo (RN-COM-005). */
  const revisarAntesDeSalir = (b: Borrador, verbo: string): boolean => {
    const falta = faltaEnBorrador(b);
    if (!falta) return true;
    notificar(`${falta} antes de ${verbo}`);
    setDialogo("tipo");
    return false;
  };

  /** Marca (o desmarca) el pedido como comida del personal. El PIN del
   * encargado se canjea acá por la elevación: si el PIN no vale, el cajero
   * se entera antes de mandar nada a cocina. */
  const marcarConsumoPersonal = async (datosConsumo: {
    motivo: string;
    encargado: { username: string; pin: string };
  }) => {
    setOcupado(true);
    try {
      const { autorizacion } = await api.autorizar(
        datosConsumo.encargado.username,
        datosConsumo.encargado.pin,
        "sales.registrar_consumo_personal",
      );
      parchar({
        consumoMotivo: datosConsumo.motivo,
        consumoAutorizacion: autorizacion,
      });
      setSeleccion(new Set());
      setDialogo(null);
      notificar("Pedido marcado como consumo de personal: no se cobra");
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo autorizar el consumo de personal"));
    } finally {
      setOcupado(false);
    }
  };

  const enviar = async () => {
    if (!activo || !revisarAntesDeSalir(activo, "enviar")) return;
    setOcupado(true);
    try {
      const venta = await api.crearVenta(cuerpoVenta(activo));
      parchar({ ventaId: venta.id, numeroOrden: venta.numero_orden });
      setSeleccion(new Set());
      notificar(`Orden #${venta.numero_orden} enviada a cocina`);
      datos.mesas.recargar();
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
    propina: number,
  ) => {
    if (!activo) return;
    setOcupado(true);
    try {
      const { ventaId, numero } = await asegurarVenta(activo);
      await registrarPagos(ventaId, pagos, doc, nombre);
      if (propina > 0) await registrarPropina(numero, propina);
      notificar(
        `Orden #${numero} cobrada · ${soles(totalBorrador(activo))} · ${
          doc.length === 11 ? "factura" : "boleta"
        } emitida`,
      );
      setDialogo(null);
      cerrarPedido(activo.id);
      datos.mesas.recargar();
      datos.cobrados.recargar();
      datos.abiertas.recargar();
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo completar el cobro"));
    } finally {
      setOcupado(false);
    }
  };

  /** Ingreso de caja aparte, no toca la venta ni el comprobante (decisión
   * del usuario, 2026-08-01): un problema al registrarla no debe deshacer
   * un cobro que ya se completó. */
  const registrarPropina = async (numeroOrden: number | null, propina: number) => {
    if (!datos.caja) return;
    try {
      await api.registrarMovimientoCaja(datos.caja.apertura_caja_id, {
        tipo: "ingreso",
        monto: String(propina),
        motivo: `Propina orden #${numeroOrden ?? "?"}`,
        idempotency_key: claveIdempotencia("propina"),
      });
    } catch (e) {
      notificar(mensajeDe(e, "El cobro se hizo, pero la propina no se registró"));
    }
  };

  /** Si el pedido nunca pasó por cocina, la venta nace en el cobro. */
  const asegurarVenta = async (b: Borrador) => {
    if (b.ventaId) return { ventaId: b.ventaId, numero: b.numeroOrden };
    const venta = await api.crearVenta(cuerpoVenta(b));
    return { ventaId: venta.id, numero: venta.numero_orden };
  };

  /** Reabre una orden ya confirmada (mesa en curso, o para llevar/delivery
   * enviado a cocina) en una pestaña editable — con sus líneas reales, no
   * las que el navegador todavía recordara de antes de recargar. */
  const reabrirOrden = async (info: {
    ventaId: string;
    numeroOrden: number | null;
    tipo: Borrador["tipo"];
    mesaId: string | null;
    mesaNumero: number | null;
    comensales: number | null;
  }) => {
    const yaAbierto = borradores.find((b) => b.ventaId === info.ventaId);
    if (yaAbierto) {
      setActivoId(yaAbierto.id);
      return;
    }
    setOcupado(true);
    try {
      const items = await api.itemsDeVenta(info.ventaId);
      const b: Borrador = {
        id: crypto.randomUUID(),
        tipo: info.tipo,
        mesaId: info.mesaId,
        mesaNumero: info.mesaNumero,
        comensales: info.comensales,
        direccion: null,
        cliente: null,
        lineas: items.map(lineaDesdeVentaItem),
        ventaId: info.ventaId,
        numeroOrden: info.numeroOrden,
        hora: hora(),
        // Reabrir es para seguir cobrando una orden en curso; un consumo de
        // personal ya no admite cambios de tipo ni cobro (RN-COM-025).
        consumoMotivo: null,
        consumoAutorizacion: null,
      };
      setBorradores((bs) => [...bs, b]);
      setActivoId(b.id);
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo abrir el pedido"));
    } finally {
      setOcupado(false);
    }
  };

  const elegirMesa = (mesa: MesaEnMapa) => {
    if (mesa.venta_id) {
      reabrirOrden({
        ventaId: mesa.venta_id,
        numeroOrden: mesa.numero_orden,
        tipo: "mesa",
        mesaId: mesa.id,
        mesaNumero: mesa.numero,
        comensales: mesa.comensales,
      });
      setVista("catalogo");
      return;
    }
    abrirNuevo(mesa);
    setVista("catalogo");
  };

  const crearCliente = async (entrada: {
    nombre: string;
    telefono: string;
    numero_documento: string;
    direccion: string;
    fecha_nacimiento: string;
  }) => {
    try {
      await api.crearCliente({
        nombre: entrada.nombre,
        telefono: entrada.telefono,
        numero_documento: entrada.numero_documento || null,
        direccion: entrada.direccion || null,
        fecha_nacimiento: entrada.fecha_nacimiento || null,
      });
      const [encontrado] = await api.buscarClientes(entrada.telefono);
      if (encontrado) {
        parchar({ cliente: encontrado, direccion: encontrado.direccion });
        notificar(`${encontrado.nombre} guardado y asignado`);
      }
      setDialogo(null);
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo crear el cliente"));
    }
  };

  /** Sin línea alguna es un pedido vacío: no hay nada que anular en el
   * servidor, así que descartar la pestaña alcanza. */
  const anularPedido = async () => {
    if (!activo || activo.lineas.length === 0) return;
    if (!activo.ventaId) {
      cerrarPedido(activo.id);
      notificar("Pedido descartado");
      return;
    }
    setOcupado(true);
    try {
      await api.anularVenta(activo.ventaId);
      cerrarPedido(activo.id);
      notificar(`Orden #${activo.numeroOrden} anulada`);
      datos.mesas.recargar();
      datos.abiertas.recargar();
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo anular el pedido"));
    } finally {
      setOcupado(false);
    }
  };

  /** Quitar una línea ya enviada a cocina repone insumo (RN-COM-020): el
   * PIN que teclea el supervisor es el mismo token de `POST /auth/autorizar`
   * que verifica `anular-lineas`. */
  const anularLineaEnviada = async (
    lineaId: string,
    encargado: { username: string; pin: string },
  ) => {
    if (!activo?.ventaId) return;
    setOcupado(true);
    try {
      const elevacion = await api.autorizar(
        encargado.username,
        encargado.pin,
        "sales.anular",
      );
      const venta = await api.anularLineas(activo.ventaId, {
        venta_item_ids: [lineaId],
        motivo: "Anulado desde PDV",
        autorizacion: elevacion.autorizacion,
      });
      setLineaEnEdicion(null);
      if (venta.estado === "anulada") {
        cerrarPedido(activo.id);
        notificar(`Orden #${activo.numeroOrden} anulada: no quedaron líneas`);
      } else {
        parchar({ lineas: activo.lineas.filter((l) => l.id !== lineaId) });
        notificar("Línea anulada");
      }
      datos.mesas.recargar();
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo anular la línea"));
    } finally {
      setOcupado(false);
    }
  };

  const verOrdenAbierta = (venta: Venta) => {
    reabrirOrden({
      ventaId: venta.id,
      numeroOrden: venta.numero_orden,
      tipo: (venta.modalidad as Borrador["tipo"]) ?? "takeout",
      mesaId: venta.mesa_id,
      mesaNumero: null,
      comensales: venta.comensales,
    });
    setVista("catalogo");
  };

  const verCobrado = async (venta: Venta) => {
    setCobradoAVer(venta);
    try {
      const p = await api.precuenta(venta.id);
      setPrecuentaAVer(p.texto);
    } catch (e) {
      setPrecuentaAVer(mensajeDe(e, "No se pudo cargar el comprobante"));
    }
  };

  const bloqueo = bloqueoDeCaja(datos.cajaResuelta, datos.fallaCaja);
  if (bloqueo) return bloqueo;

  return (
    <main className="pdv">
      <header className="pdv-top">
        <div className="pdv-marca">
          <strong>Punto de venta</strong>
          <small>Serie {puntoVenta.serieBoleta}</small>
        </div>
        <EstadoCaja caja={datos.caja} onClick={() => setDialogo("cierre")} />
        <span className="pdv-spacer" />
        <span className="pdv-meta">{hora()}</span>
      </header>

      <div className="pdv-shell">
        <Catalogo
          carta={datos.carta}
          mesas={datos.mesas}
          cobrados={datos.cobrados}
          abiertas={datos.abiertas}
          vista={vista}
          onVista={setVista}
          onProducto={agregarProducto}
          onMesa={elegirMesa}
          onOrdenAbierta={verOrdenAbierta}
          onVerCobrado={verCobrado}
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
          onAnular={anularPedido}
          onEnviar={enviar}
          onCobrar={() => {
            if (activo && revisarAntesDeSalir(activo, "cobrar")) setDialogo("cobro");
          }}
          onConsumoPersonal={() => {
            // Quitar la marca no necesita firma: deja el pedido como venta
            // normal, que es el camino que sí cobra.
            if (activo?.consumoMotivo) {
              parchar({ consumoMotivo: null, consumoAutorizacion: null });
              notificar("Pedido vuelve a ser una venta normal");
              return;
            }
            setDialogo("consumo");
          }}
        />
      </div>

      {aviso && <p className="pdv-aviso">{aviso}</p>}

      <DialogoApertura
        abierto={!datos.caja}
        pos={datos.pos}
        onAbrir={abrirCaja}
        ocupado={ocupado}
      />
      <DialogoCierre
        abierto={dialogo === "cierre"}
        posVerificados={posDelTurno}
        onCerrar={() => setDialogo(null)}
        onCerrarCaja={cerrarCaja}
        ocupado={ocupado}
      />
      <DialogoProducto
        linea={lineaEnEdicion}
        item={
          // La línea puede apuntar al producto o a una de sus variantes
          // (al reabrirla, `productoId` ya es la variante elegida).
          datos.carta.find(
            (c) =>
              c.producto_comercial_id === lineaEnEdicion?.productoId ||
              c.variantes.some(
                (v) => v.producto_comercial_id === lineaEnEdicion?.productoId,
              ),
          ) ?? null
        }
        enviado={Boolean(activo?.ventaId)}
        onCerrar={() => setLineaEnEdicion(null)}
        onGuardar={(l) => {
          const yaExiste = activo?.lineas.some((x) => x.id === l.id);
          parchar({
            lineas: yaExiste
              ? (activo?.lineas.map((x) => (x.id === l.id ? l : x)) ?? [])
              : [...(activo?.lineas ?? []), l],
          });
          setLineaEnEdicion(null);
        }}
        onQuitar={(id) => {
          parchar({ lineas: activo?.lineas.filter((x) => x.id !== id) ?? [] });
          setLineaEnEdicion(null);
        }}
        onAnularLinea={anularLineaEnviada}
      />
      <DialogoTipo
        abierto={dialogo === "tipo"}
        borrador={activo}
        mesas={datos.mesas.datos}
        onCerrar={() => setDialogo(null)}
        onConfirmar={(cambios) => {
          parchar(cambios);
          setDialogo(null);
        }}
      />
      <DialogoConsumoPersonal
        abierto={dialogo === "consumo"}
        ocupado={ocupado}
        onCerrar={() => setDialogo(null)}
        onConfirmar={marcarConsumoPersonal}
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
      <Dialogo
        titulo={tituloComprobante(cobradoAVer)}
        abierto={cobradoAVer !== null}
        onCerrar={() => setCobradoAVer(null)}
      >
        <pre className="pdv-precuenta">{precuentaAVer || "Cargando…"}</pre>
      </Dialogo>
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
    restas: [],
    grupoCobro: 1,
  };
}

/** El id de la línea es el del `venta_item` real: si el cajero la quita
 * después, `anular-lineas` necesita ese id, no uno inventado en el
 * navegador (RN-COM-020). */
function lineaDesdeVentaItem(item: VentaItem): LineaBorrador {
  return {
    id: item.id,
    productoId: item.producto_comercial_id,
    nombre: item.nombre,
    precio: Number(item.precio_unitario),
    cantidad: Number(item.cantidad),
    nota: "",
    extras: item.extras.map((e) => ({
      productoId: e.producto_comercial_id,
      nombre: e.nombre,
      precio: Number(e.precio_unitario),
      cantidad: Number(e.cantidad),
    })),
    // La venta ya existe: sus restas se guardaron con la línea y no viajan
    // en este contrato. Reabrirla para editar cantidad no las pierde —
    // `anular-lineas` + línea nueva es el camino de corregir lo enviado
    // (RN-COM-020), no un PATCH de la línea original.
    restas: [],
    grupoCobro: item.grupo_cobro,
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
