"use client";

import { useCallback, useEffect, useState } from "react";

import { esSinPermiso, type Falla } from "@/lib/carga";
import { tienePermiso } from "@/lib/permisos";
import {
  api,
  claveIdempotencia,
  ErrorApi,
  soles,
  type CajaAbierta,
  type ClienteBuscado,
  type ComprobanteDeVenta,
  type ItemDeCarta,
  type ItemDeVentaNueva,
  type MesaEnMapa,
  type Venta,
  type VentaItem,
  type VentaNueva,
} from "@/lib/pdv";

import Catalogo from "./catalogo";
import DespachoEnPdv from "./despacho";
import {
  DialogoApertura,
  DialogoAutorizacion,
  DialogoCierre,
  DialogoCliente,
  DialogoCobro,
  DialogoConsumoPersonal,
  DialogoDescuento,
  Dialogo,
  DialogoMotivoAnulacion,
  DialogoMover,
  DialogoProducto,
  DialogoTipo,
} from "./dialogos";
import Ticket from "./ticket";
import {
  faltaEnBorrador,
  lineasPendientes,
  totalBorrador,
  totalLinea,
  type Borrador,
  type DestinoMover,
  type LineaBorrador,
} from "./tipos";
import { useBorradoresPdv } from "./use-borradores-pdv";
import { useCajaPdv } from "./use-caja-pdv";
import { useImpresionPdv } from "./use-impresion-pdv";
import { useDatosPdv } from "./use-datos-pdv";
import { UBICACION_VACIA, type Ubicacion } from "@/components/direccion/ubicacion";

type Props = {
  sucursalId: string;
  /** Las del cajero, y solo si tiene más de una: el selector no le sirve a
   * quien trabaja en un local (ADR-073). */
  sucursales: { id: string; nombre: string }[];
  /** Los del cajero. Solo deciden si se le ofrece traer un documento de
   * RENIEC/SUNAT: el resto del PDV ya está detrás del permiso de la caja. */
  permisos: string[];
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
    notaCocina: "",
    direccion: null,
    costoEntrega: null,
    ubicacion: UBICACION_VACIA,
    cliente: null,
    lineas: [],
    ventaId: null,
    numeroOrden: null,
    hora: hora(),
    consumoMotivo: null,
    consumoAutorizacion: null,
    descuento: null,
    cupon: null,
    promociones: [],
  };
}

/** Un pedido que todavía no es nada: sin líneas, sin mesa, sin cliente y sin
 * haber salido a cocina. Se puede cerrar sin preguntar y no vale la pena
 * abrir otro igual al lado. */
function estaVacio(b: Borrador): boolean {
  return (
    b.lineas.length === 0 &&
    !b.ventaId &&
    !b.mesaId &&
    !b.cliente &&
    !b.consumoMotivo
  );
}

/**
 * La línea del borrador, tal como la espera el servidor.
 *
 * Una sola función porque hay **dos** caminos que mandan líneas —confirmar
 * el pedido y agregar a una orden ya enviada— y armaban el cuerpo cada uno
 * por su lado. Con el cuerpo duplicado, agregar un campo en un solo sitio
 * significa que sumar una pizza a una mesa abierta la manda sin sabores y
 * el 409 aparece recién ahí, cuando el cajero ya cree que terminó.
 */
/** El texto vacío que el PDV usa para "sin nota" es `null` en el contrato:
 * una cadena vacía guardada es una nota que el KDS pinta como línea en
 * blanco. Vive fuera de los componentes para no sumarles ramas. */
const vacioANull = (texto: string): string | null => texto.trim() || null;

function cuerpoLinea(l: LineaBorrador): ItemDeVentaNueva {
  return {
    producto_comercial_id: l.productoId,
    cantidad: String(l.cantidad),
    grupo_cobro: l.grupoCobro,
    extras: l.extras.map((e) => ({
      producto_comercial_id: e.productoId,
      cantidad: String(e.cantidad),
    })),
    sin_articulo_ids: l.restas.map((r) => r.articuloId),
    valores_variante_ids: l.valores.map((v) => v.ptavId),
    // Hasta ADR-075 esta línea faltaba y la nota se quedaba en el navegador:
    // el diálogo la pedía, el cocinero nunca la veía.
    nota: vacioANull(l.nota),
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

/** El interruptor entre carta y ticket, para el ancho donde no entran los
 * dos. Lleva el total del pedido activo porque en ese ancho el ticket no
 * está a la vista y el cajero necesita saber que hay algo cargado. */
function CambiarPanel({
  panel,
  activo,
  onCambiar,
}: {
  panel: "carta" | "ticket";
  activo: Borrador | null;
  onCambiar: () => void;
}) {
  const total = activo ? totalBorrador(activo) : 0;
  const monto = panel === "carta" && total > 0 ? ` · ${soles(total)}` : "";
  return (
    <button
      type="button"
      className="pdv-cambia-panel"
      data-testid="cambiar-panel"
      onClick={onCambiar}
    >
      {panel === "carta" ? "Pedido" : "Carta"}
      {monto}
    </button>
  );
}

/**
 * Cambiar de local sin pasar por el back office.
 *
 * Solo aparece con más de una sucursal asignada. Navega en vez de guardar un
 * estado: la sucursal va en la URL (`?sucursal=`), así que la tablet del
 * local se queda con su enlace y el servidor vuelve a resolver el punto de
 * venta y la caja de ese sitio — que es lo que hay que rehacer, no un
 * filtro de pantalla.
 */
function SelectorSucursal({
  actual,
  sucursales,
}: {
  actual: string;
  sucursales: { id: string; nombre: string }[];
}) {
  if (sucursales.length <= 1) return null;
  return (
    <select
      className="pdv-selector-sucursal"
      aria-label="Sucursal"
      value={actual}
      onChange={(e) => {
        window.location.href = `/pdv?sucursal=${e.target.value}`;
      }}
    >
      {sucursales.map((s) => (
        <option key={s.id} value={s.id}>
          {s.nombre}
        </option>
      ))}
    </select>
  );
}

/**
 * Bloquea la pantalla ahora mismo (RN-POS-014).
 *
 * El bloqueo por inactividad ya existía, pero son cinco minutos: quien se
 * aleja de la caja no tiene forma de cerrarla al irse y deja la sesión
 * operable a quien pase. Esto es el gesto explícito — el mismo overlay, con
 * su PIN y su "Cambiar de usuario".
 *
 * Va por evento y no subiendo el estado a este componente: el overlay vive
 * fuera del PDV a propósito (es un `<dialog>` del top layer del navegador,
 * hermano de `PdvCliente` en `page.tsx`), y pasarle una prop obligaría a
 * mover el bloqueo adentro y perder eso.
 */
function BotonBloquear() {
  return (
    <button
      type="button"
      className="pdv-boton-icono"
      title="Bloquear la pantalla"
      aria-label="Bloquear la pantalla"
      onClick={() => window.dispatchEvent(new Event("pdv:bloquear"))}
    >
      🔒
    </button>
  );
}

/** Las promociones que el pedido activó solo. Un fallo acá no puede
 * frenar la caja: el total que manda es el del servidor, y esto es lo que se
 * muestra para poder explicarlo. */
async function promocionesDe(ventaId: string) {
  const filas = await api.promocionesDeVenta(ventaId).catch(() => []);
  return filas.map((p) => ({ nombre: p.nombre, monto: Number(p.monto) }));
}

/** El descuento ya aplicado, tal como lo devuelve el servidor. Fuera del
 * componente porque es traducción de contrato, no estado de pantalla. */
function descuentoDeVenta(venta: Venta): Borrador["descuento"] {
  if (!venta.descuento_modo || venta.descuento_valor === null) return null;
  return {
    modo: venta.descuento_modo,
    valor: Number(venta.descuento_valor),
    motivo: venta.descuento_motivo ?? "",
  };
}

/** Si la línea abierta en el diálogo ya salió a cocina. Fuera del
 * componente para no sumarle ramas a su cuerpo, que ya está en el tope. */
const yaEstaEnCocina = (l: LineaBorrador | null): boolean => l?.enviada ?? false;

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

export default function PdvCliente({
  sucursalId,
  sucursales,
  permisos,
  puntoVenta,
}: Props) {
  const datos = useDatosPdv(puntoVenta.id, sucursalId);
  const [borradores, setBorradores] = useState<Borrador[]>([nuevoBorrador()]);
  const [activoId, setActivoId] = useState<string | null>(null);
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set());
  /** Qué panel ocupa la pantalla cuando no entran los dos: en tablet vertical
   * y en teléfono la carta y el ticket comparten el mismo lugar. En el ancho
   * de mostrador este estado no se usa — los dos paneles se ven a la vez. */
  const [panel, setPanel] = useState<"carta" | "ticket">("carta");
  const [vista, setVista] = useState<"catalogo" | "mesas" | "abiertas" | "cobrados">(
    "catalogo",
  );
  const [dialogo, setDialogo] = useState<
    | "cliente"
    | "tipo"
    | "cobro"
    | "cierre"
    | "consumo"
    | "mover"
    | "descuento"
    | null
  >(null);
  const [lineaEnEdicion, setLineaEnEdicion] = useState<LineaBorrador | null>(null);
  const [cobradoAVer, setCobradoAVer] = useState<Venta | null>(null);
  /**
   * Lo que el servidor dice que falta cobrar de la cuenta única.
   *
   * `null` = todavía no se sabe, o el pedido nunca se envió (no hay venta
   * contra la que preguntar) y ahí el borrador es la única fuente posible.
   *
   * Existe porque el total del navegador y el del servidor podían discrepar
   * —el flete de una orden reabierta, el prorrateo del descuento entre
   * cuentas— y entonces el botón "Exacto" ofrecía un número que el cobro
   * rechazaba por exceder el saldo, con el monto exacto en pantalla. El
   * número que valida el pago tiene que ser el mismo que lo propone.
   */
  const [saldoServidor, setSaldoServidor] = useState<number | null>(null);
  const [precuentaAVer, setPrecuentaAVer] = useState("");
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);
  // Solo se enciende si el servidor dijo que a este usuario no le alcanza.
  const [firmandoAnulacion, setFirmandoAnulacion] = useState(false);
  // Qué línea espera la firma del supervisor, o `null` si ninguna.
  const [lineaFirmando, setLineaFirmando] = useState<string | null>(null);
  // Qué línea se está quitando, mientras se pregunta el motivo.
  const [lineaAQuitar, setLineaAQuitar] = useState<{
    id: string;
    nombre: string;
  } | null>(null);
  // El motivo tecleado, para poder repetirlo si el servidor pide firma.
  const [motivoAnulacion, setMotivoAnulacion] = useState("");
  // La cola de despacho, encima del PDV. Se resuelve al abrirla.
  const [viendoDespacho, setViendoDespacho] = useState(false);

  const activo = borradores.find((b) => b.id === activoId) ?? borradores[0] ?? null;

  /** Los recuperados **reemplazan** a la pestaña en blanco del arranque, no
   * se suman: si no, cada recarga dejaría una pestaña vacía por encima de lo
   * que se estaba armando.
   *
   * Y se completan contra un borrador nuevo, no se usan crudos. El contenido
   * guardado es JSONB opaco (ADR-074), así que un ticket que se guardó antes
   * de que el PDV tuviera un campo vuelve sin él: la pantalla lo lee como
   * `undefined` y React convierte su input controlado en uno sin control —
   * el campo deja de responder y nadie sabe por qué. Rellenar con el molde
   * de hoy es lo que hace que el formato del borrador pueda crecer sin
   * migrar nada. */
  const restaurarBorradores = useCallback((guardados: Borrador[]) => {
    const completos = guardados.map((b) => ({ ...nuevoBorrador(), ...b }));
    setBorradores(completos);
    setActivoId(completos[0].id);
  }, []);

  /** Los borradores viven en el servidor (ADR-074): recargar la página o
   * cambiar de turno ya no borra las pestañas de pedido. */
  const persistencia = useBorradoresPdv(puntoVenta.id, borradores, restaurarBorradores);

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

  const impresion = useImpresionPdv({ setOcupado, notificar, mensajeDe });

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

  /** Abre un pedido nuevo, o reusa el vacío que ya está abierto.
   *
   * Sin esto, cada toque del "+" apilaba una pestaña más: quedaban diez
   * pedidos vacíos que no se podían cerrar y que hacían ilegible la columna
   * derecha. Un borrador sin líneas y sin destino no es un pedido distinto de
   * otro igual — es el mismo pedido sin empezar.
   */
  const abrirNuevo = (mesa?: MesaEnMapa) => {
    if (!mesa) {
      const vacio = borradores.find(estaVacio);
      if (vacio) {
        setActivoId(vacio.id);
        return vacio;
      }
    }
    const b = nuevoBorrador(mesa);
    setBorradores((bs) => [...bs, b]);
    setActivoId(b.id);
    return b;
  };

  const cerrarPedido = (id: string) => {
    persistencia.descartar(id);
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
    // Un pedido ya enviado admite líneas nuevas (RN-COM-029): la mesa que
    // pide de a poco no tiene por qué terminar con dos cuentas. Se guardan
    // contra el servidor al confirmar la línea, no al enviar.
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
      nota_cocina: vacioANull(b.notaCocina),
      referencia_atencion: b.tipo === "mesa" ? null : (b.cliente?.nombre ?? null),
      // Solo el delivery lleva dirección; el costo del reparto lo calcula
      // el servidor y se congela en la venta (ADR-054).
      ...(b.tipo === "delivery"
        ? { direccion_entrega: b.direccion, ...b.ubicacion }
        : {}),
      // Comida del personal: el servidor pone los precios en cero y exige la
      // elevación del encargado (RN-COM-025).
      ...(b.consumoMotivo
        ? {
            tipo: "consumo_personal",
            consumo_motivo: b.consumoMotivo,
            autorizacion: b.consumoAutorizacion ?? undefined,
          }
        : {}),
      items: b.lineas.map(cuerpoLinea),
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

  /**
   * Manda a cocina lo que todavía no salió.
   *
   * Dos caminos con el mismo gesto: si el pedido nunca se envió, crea la
   * venta; si ya existe, agrega el aumento — que el servidor mete en una
   * tanda propia y el KDS pinta como una comanda nueva (ADR-075).
   *
   * En los dos casos se relee la orden completa: ni `crearVenta` ni
   * `agregarLineas` devuelven el id que el servidor le puso a cada línea, y
   * quitar o mover una línea después (RN-COM-020, RN-COM-043) manda ese id,
   * no el uuid que el navegador inventó mientras era un borrador.
   */
  const enviar = async () => {
    if (!activo || !revisarAntesDeSalir(activo, "enviar")) return;
    const pendientes = lineasPendientes(activo);
    if (pendientes.length === 0) return;
    setOcupado(true);
    try {
      const esAumento = Boolean(activo.ventaId);
      const venta = esAumento
        ? await api.agregarLineas(activo.ventaId!, pendientes.map(cuerpoLinea))
        : await api.crearVenta(cuerpoVenta(activo));
      const items = await api.itemsDeVenta(venta.id);
      parchar({
        ventaId: venta.id,
        numeroOrden: venta.numero_orden,
        lineas: items.map(lineaDesdeVentaItem),
        // El servidor las reevalúa entero en cada cambio del pedido
        // (ADR-076): el aumento pudo activar un 2x1 que antes no se cumplía.
        promociones: await promocionesDe(venta.id),
      });
      setSeleccion(new Set());
      notificar(
        esAumento
          ? `Aumento enviado a la orden #${venta.numero_orden}`
          : `Orden #${venta.numero_orden} enviada a cocina`,
      );
      datos.mesas.recargar();
      datos.abiertas.recargar();
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo enviar el pedido"));
    } finally {
      setOcupado(false);
    }
  };

  /**
   * Abre el cobro con el saldo que dice el servidor.
   *
   * Solo con la venta ya creada y cobrando la cuenta entera: al cobrar
   * seleccionados, las líneas todavía no se movieron a su cuenta y el
   * servidor no tiene ese grupo que consultar.
   */
  const abrirCobro = () => {
    if (!activo || !revisarAntesDeSalir(activo, "cobrar")) return;
    setSaldoServidor(null);
    if (activo.ventaId && seleccion.size === 0) {
      api
        .saldoDeVenta(activo.ventaId)
        .then((cuentas) => {
          const unica = cuentas.find((c) => c.grupo_cobro === 1);
          if (unica) setSaldoServidor(Number(unica.saldo));
        })
        .catch(() => {
          // Se cobra igual con el total del borrador: quedarse sin poder
          // cobrar por un dato de apoyo sería peor que la diferencia que
          // este dato viene a evitar.
        });
    }
    setDialogo("cobro");
  };

  const confirmarCobro = async (
    pagos: Array<{ medioId: string; monto: number }>,
    doc: string,
    nombre: string,
    propina: number,
    gravadoIgv: boolean | null,
  ) => {
    if (!activo) return;
    // Cobrar solo lo seleccionado es "separar la cuenta" (RN-COM-018): la
    // selección se mueve a una cuenta nueva de la MISMA orden y se cobra
    // solo esa (mismo mecanismo que "mover productos", RN-COM-043). Sin
    // selección, o con todo seleccionado, se cobra la orden entera de
    // siempre.
    const seleccionParcial = seleccion.size > 0 && seleccion.size < activo.lineas.length;
    if (seleccionParcial && !activo.ventaId) {
      // El id de una línea de un borrador sin enviar es local al
      // navegador: separar la cuenta exige la línea ya enviada, con su id
      // real (igual que "mover productos").
      notificar("Envía el pedido antes de cobrar solo lo seleccionado");
      return;
    }
    setOcupado(true);
    try {
      const { ventaId, numero } = await asegurarVenta(activo);
      let grupoCobro = 1;
      if (seleccionParcial) {
        const siguienteGrupo = Math.max(0, ...activo.lineas.map((l) => l.grupoCobro)) + 1;
        await api.moverLineas(ventaId, {
          venta_item_ids: [...seleccion],
          grupo_cobro: siguienteGrupo,
        });
        grupoCobro = siguienteGrupo;
      }
      await registrarPagos(ventaId, pagos, doc, nombre, grupoCobro, gravadoIgv);
      if (propina > 0) await registrarPropina(numero, propina);
      notificar(
        `Orden #${numero} cobrada · ${soles(totalACobrar(activo, seleccion))} · ${
          doc.length === 11 ? "factura" : "boleta"
        } emitida`,
      );
      setDialogo(null);
      if (seleccionParcial) {
        // El resto del pedido sigue abierto: solo se cobró esa cuenta.
        const idsCobrados = seleccion;
        setBorradores((bs) =>
          bs.map((b) =>
            b.id === activo.id
              ? { ...b, lineas: b.lineas.filter((l) => !idsCobrados.has(l.id)) }
              : b,
          ),
        );
        setSeleccion(new Set());
      } else {
        cerrarPedido(activo.id);
      }
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
      // La nota y el descuento salen de la lista de cuentas abiertas, que ya
      // trae la venta entera: pedirla de nuevo sería un viaje para dos
      // campos. Los dos caminos de reapertura —el mapa de mesas y la
      // pestaña de cuentas— miran acá, así que no pueden discrepar.
      const venta = datos.abiertas.datos.find((v) => v.id === info.ventaId);
      const b: Borrador = {
        id: crypto.randomUUID(),
        tipo: info.tipo,
        mesaId: info.mesaId,
        mesaNumero: info.mesaNumero,
        comensales: info.comensales,
        notaCocina: venta?.nota_cocina ?? "",
        direccion: null,
        costoEntrega: null,
        ubicacion: UBICACION_VACIA,
        cliente: null,
        lineas: items.map(lineaDesdeVentaItem),
        ventaId: info.ventaId,
        numeroOrden: info.numeroOrden,
        hora: hora(),
        // Reabrir es para seguir cobrando una orden en curso; un consumo de
        // personal ya no admite cambios de tipo ni cobro (RN-COM-025).
        consumoMotivo: null,
        consumoAutorizacion: null,
        descuento: venta ? descuentoDeVenta(venta) : null,
        cupon: null,
        promociones: await promocionesDe(info.ventaId),
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

  /** Busca el cliente recién dado de alta (o el que ya existía) y lo pega al
   * pedido. Devuelve si lo encontró. */
  const asignarBuscando = async (
    consulta: string,
    queLePaso: string,
  ): Promise<boolean> => {
    const [encontrado] = await api.buscarClientes(consulta).catch(() => []);
    if (!encontrado) return false;
    parchar({
      cliente: encontrado,
      direccion: encontrado.direccion,
      ubicacion: encontrado,
    });
    notificar(`${encontrado.nombre} ${queLePaso}`);
    return true;
  };

  const crearCliente = async (entrada: {
    nombre: string;
    telefono: string;
    numero_documento: string;
    direccion: string;
    fecha_nacimiento: string;
    ubicacion: Ubicacion;
  }) => {
    // Con lo que se pueda buscar después. El teléfono no siempre está: un
    // cliente se puede dar de alta solo con su documento, y buscar por un
    // teléfono vacío devolvía la lista entera —o nada— y el alta quedaba sin
    // asignarse al pedido.
    const aBuscar = entrada.telefono || entrada.numero_documento;
    try {
      await api.crearCliente({
        nombre: entrada.nombre,
        telefono: entrada.telefono,
        numero_documento: entrada.numero_documento || null,
        direccion: entrada.direccion || null,
        fecha_nacimiento: entrada.fecha_nacimiento || null,
        ...entrada.ubicacion,
      });
      if (await asignarBuscando(aBuscar, "guardado y asignado")) setDialogo(null);
    } catch (e) {
      // 409 = esa persona ya es cliente del grupo. Pasa cada vez que un
      // trabajador quiere consumir en el local: su persona ya existe porque
      // trabaja acá. El camino correcto es usar ese cliente, no dejar al
      // cajero contra un error que solo dice que el alta no se hizo.
      const yaEstaba = e instanceof ErrorApi && e.status === 409;
      if (yaEstaba && (await asignarBuscando(aBuscar, "ya estaba registrado"))) {
        setDialogo(null);
        return;
      }
      notificar(mensajeDe(e, "No se pudo crear el cliente"));
    }
  };

  /** Sin línea alguna es un pedido vacío: no hay nada que anular en el
   * servidor, así que descartar la pestaña alcanza. */
  /** Anula la orden. Sin firma primero: quien tiene `sales.anular` —un
   * encargado— no debería teclear su propio PIN para anular su pedido. Si el
   * servidor dice que no le alcanza, recién ahí se pide la del supervisor. */
  const anularVenta = async (ventaId: string, autorizacion?: string) => {
    setOcupado(true);
    try {
      await api.anularVenta(ventaId, autorizacion);
      setFirmandoAnulacion(false);
      cerrarPedido(activo!.id);
      notificar(`Orden #${activo!.numeroOrden} anulada`);
      datos.mesas.recargar();
      datos.abiertas.recargar();
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 403 && !autorizacion) {
        setFirmandoAnulacion(true);
        return;
      }
      notificar(mensajeDe(e, "No se pudo anular el pedido"));
    } finally {
      setOcupado(false);
    }
  };

  /** Guarda la línea en el borrador. **Nunca la manda al servidor.**
   *
   * Sobre una orden ya abierta esto era una llamada a `agregar-lineas` en el
   * momento de confirmar el diálogo del producto, y el ítem aparecía en el
   * KDS al instante, dentro de la misma pastilla del pedido original
   * (ADR-075). Para la cocina eso era indistinguible de lo que llevaba media
   * hora esperando, y el mesero no tenía manera de mandar dos cosas juntas.
   *
   * Ahora la línea queda pendiente y sale con "Enviar aumento", que es el
   * mismo gesto que el primer envío: se marca todo, se revisa y se confirma
   * una vez. */
  const guardarLinea = (l: LineaBorrador) => {
    if (!activo) return;
    const yaExiste = activo.lineas.some((x) => x.id === l.id);
    parchar({
      lineas: yaExiste
        ? activo.lineas.map((x) => (x.id === l.id ? l : x))
        : [...activo.lineas, l],
    });
    setLineaEnEdicion(null);
  };

  const anularPedido = async () => {
    if (!activo || activo.lineas.length === 0) return;
    if (!activo.ventaId) {
      cerrarPedido(activo.id);
      notificar("Pedido descartado");
      return;
    }
    await anularVenta(activo.ventaId);
  };

  const firmarAnulacion = async (encargado: { username: string; pin: string }) => {
    if (!activo?.ventaId) return;
    setOcupado(true);
    try {
      const elevacion = await api.autorizar(
        encargado.username,
        encargado.pin,
        "sales.anular",
      );
      await anularVenta(activo.ventaId, elevacion.autorizacion);
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo autorizar la anulación"));
    } finally {
      setOcupado(false);
    }
  };

  /** Quitar una línea ya enviada repone insumo (RN-COM-020). Dentro de los
   * 5 minutos lo hace el cajero solo (RN-COM-029); después el servidor pide
   * la firma del supervisor y recién ahí el diálogo la pide — el PIN que
   * teclea es el token de `POST /auth/autorizar` que verifica
   * `anular-lineas`.
   *
   * El motivo lo teclea quien quita, y se recuerda para el reintento con
   * firma: pedirlo dos veces por la misma anulación sería castigar al cajero
   * por un permiso que no tiene. */
  const anularLineaEnviada = async (
    lineaId: string,
    motivo: string,
    encargado?: { username: string; pin: string },
  ) => {
    if (!activo?.ventaId) return;
    setOcupado(true);
    try {
      const elevacion = encargado
        ? await api.autorizar(encargado.username, encargado.pin, "sales.anular")
        : null;
      const venta = await api.anularLineas(activo.ventaId, {
        venta_item_ids: [lineaId],
        motivo,
        ...(elevacion ? { autorizacion: elevacion.autorizacion } : {}),
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
      datos.abiertas.recargar();
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 403 && !encargado) {
        setMotivoAnulacion(motivo);
        setLineaFirmando(lineaId);
        return;
      }
      notificar(mensajeDe(e, "No se pudo anular la línea"));
    } finally {
      setOcupado(false);
    }
  };

  /** Canjea el cupón del cliente. **Sin firma** (RN-PRM-007): el descuento
   * ya estaba prometido y el cupón es la autorización. */
  const canjearCupon = async (codigo: string) => {
    if (!activo?.ventaId) return;
    setOcupado(true);
    try {
      const { monto_descuento } = await api.canjearCupon(activo.ventaId, codigo);
      parchar({ cupon: codigo });
      setDialogo(null);
      notificar(`Cupón ${codigo} canjeado: −${soles(Number(monto_descuento))}`);
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo canjear el cupón"));
    } finally {
      setOcupado(false);
    }
  };

  /** Descuento manual sobre la orden. **Con firma de supervisor**
   * (RN-COM-017): acá se regala margen a criterio de alguien, y el PIN se
   * canjea por la elevación acotada antes de tocar la venta — si no vale, el
   * cajero se entera antes de haber cambiado nada. */
  const aplicarDescuento = async (datos: {
    modo: "porcentaje" | "monto";
    valor: number;
    motivo: string;
    encargado: { username: string; pin: string };
  }) => {
    if (!activo?.ventaId) return;
    setOcupado(true);
    try {
      const { autorizacion } = await api.autorizar(
        datos.encargado.username,
        datos.encargado.pin,
        "sales.aplicar_descuento",
      );
      const venta = await api.aplicarDescuento(activo.ventaId, {
        modo: datos.modo,
        valor: String(datos.valor),
        motivo: datos.motivo,
        autorizacion,
      });
      parchar({ descuento: descuentoDeVenta(venta) });
      setDialogo(null);
      notificar("Descuento aplicado");
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo aplicar el descuento"));
    } finally {
      setOcupado(false);
    }
  };

  /** Quitarlo también lo firma un supervisor: es el mismo acto al revés, y
   * el reporte necesita saber quién deshizo qué. */
  const quitarDescuento = async (encargado: { username: string; pin: string }) => {
    if (!activo?.ventaId) return;
    setOcupado(true);
    try {
      const { autorizacion } = await api.autorizar(
        encargado.username,
        encargado.pin,
        "sales.aplicar_descuento",
      );
      await api.aplicarDescuento(activo.ventaId, { modo: null, autorizacion });
      parchar({ descuento: null });
      setDialogo(null);
      notificar("Descuento quitado");
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo quitar el descuento"));
    } finally {
      setOcupado(false);
    }
  };

  /** Mover los productos seleccionados a otra orden (RN-COM-043, ADR-071):
   * otra mesa —libre u ocupada— o un pedido para llevar/delivery. Sin PIN de
   * supervisor: el producto sigue existiendo en alguna orden abierta. */
  const moverSeleccionados = async (destino: DestinoMover) => {
    if (!activo?.ventaId || seleccion.size === 0) return;
    setOcupado(true);
    try {
      const { destino: ventaDestino } = await api.moverLineas(activo.ventaId, {
        venta_item_ids: [...seleccion],
        ...("mesaId" in destino
          ? { destino_mesa_id: destino.mesaId }
          : { destino_venta_id: destino.ventaId }),
      });
      const idsMovidos = seleccion;
      setSeleccion(new Set());
      setDialogo(null);
      notificar(`Movido a la orden #${ventaDestino.numero_orden}`);
      // La pestaña origen pierde las líneas movidas; si otra pestaña ya
      // tenía abierto el destino, se refresca con lo que el servidor diga
      // — es la única fuente de verdad después de un traslado.
      setBorradores((bs) =>
        bs.map((b) =>
          b.id === activo.id
            ? { ...b, lineas: b.lineas.filter((l) => !idsMovidos.has(l.id)) }
            : b,
        ),
      );
      if (!activo.lineas.some((l) => !idsMovidos.has(l.id))) {
        cerrarPedido(activo.id);
      }
      const pestanaDestino = borradores.find((b) => b.ventaId === ventaDestino.id);
      if (pestanaDestino) {
        const items = await api.itemsDeVenta(ventaDestino.id);
        setBorradores((bs) =>
          bs.map((b) =>
            b.id === pestanaDestino.id
              ? { ...b, lineas: items.map(lineaDesdeVentaItem) }
              : b,
          ),
        );
      }
      datos.mesas.recargar();
      datos.abiertas.recargar();
    } catch (e) {
      notificar(mensajeDe(e, "No se pudieron mover los productos"));
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
      // Del contrato y no `null` en duro: por este camino la cuenta se
      // reabre desde la pestaña de cuentas abiertas, que nunca pasó por el
      // mapa de salón — la pestaña quedaba rotulada "Mesa ?".
      mesaNumero: venta.mesa_numero,
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
        {/* Solo existe en el ancho donde los dos paneles no entran lado a
            lado (`.pdv-cambia-panel`, `pdv.css`). Antes de esto el ticket
            simplemente no estaba en una tablet vertical. */}
        <CambiarPanel
          panel={panel}
          activo={activo}
          onCambiar={() => setPanel((p) => (p === "carta" ? "ticket" : "carta"))}
        />
        <SelectorSucursal actual={sucursalId} sucursales={sucursales} />
        {/* Detrás del permiso de cocina: quien no opera el KDS no tiene por
            qué ver la cola. La autorización real la hace la API. */}
        {tienePermiso(permisos, "kds.operar") && (
          <button
            type="button"
            className="pdv-boton-icono"
            title="Ver la cola de despacho"
            aria-label="Ver la cola de despacho"
            onClick={() => setViendoDespacho(true)}
          >
            🍽
          </button>
        )}
        <BotonBloquear />
        <span className="pdv-meta">{hora()}</span>
      </header>

      <div className={`pdv-shell ver-${panel}`}>
        <Catalogo
          carta={datos.carta}
          mesas={datos.mesas}
          cobrados={datos.cobrados}
          abiertas={datos.abiertas}
          cajaAbierta={!!datos.caja}
          vista={vista}
          onVista={setVista}
          onProducto={agregarProducto}
          onMesa={elegirMesa}
          onOrdenAbierta={verOrdenAbierta}
          onVerCobrado={verCobrado}
          onImprimirComanda={impresion.imprimirComanda}
        />
        <Ticket
          borradores={borradores}
          activo={activo}
          seleccion={seleccion}
          ocupado={ocupado || !datos.caja}
          onActivar={setActivoId}
          onNuevo={() => abrirNuevo()}
          onCerrar={cerrarPedido}
          onLinea={setLineaEnEdicion}
          onAlternarSeleccion={(id) => setSeleccion(alternar(seleccion, id))}
          onLimpiarSeleccion={() => setSeleccion(new Set())}
          onMover={() => setDialogo("mover")}
          onCliente={() => setDialogo("cliente")}
          onTipo={() => setDialogo("tipo")}
          onDescuento={() => setDialogo("descuento")}
          onAnular={anularPedido}
          onEnviar={enviar}
          onCobrar={abrirCobro}
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
      <DialogoAutorizacion
        abierto={lineaFirmando !== null}
        titulo="Quitar la línea"
        detalle="Pasaron más de 5 minutos desde que salió a cocina: el insumo ya se usó, así que reponerlo lo firma un supervisor (RN-COM-020)."
        ocupado={ocupado}
        onCerrar={() => setLineaFirmando(null)}
        onFirmar={async (encargado) => {
          const id = lineaFirmando;
          setLineaFirmando(null);
          if (id) await anularLineaEnviada(id, motivoAnulacion, encargado);
        }}
      />
      <DialogoAutorizacion
        abierto={firmandoAnulacion}
        titulo="Anular el pedido"
        detalle="Ya salió a cocina y el insumo se descontó: anularlo lo repone, y lo firma un supervisor (RN-COM-020)."
        ocupado={ocupado}
        onCerrar={() => setFirmandoAnulacion(false)}
        onFirmar={firmarAnulacion}
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
        // De la LÍNEA y no del pedido: sobre una mesa abierta conviven
        // líneas que ya están en cocina con el aumento que todavía no salió
        // (ADR-075). Quitar una de esas últimas no repone nada ni necesita
        // firma — nunca existió del lado del servidor.
        enviado={yaEstaEnCocina(lineaEnEdicion)}
        onCerrar={() => setLineaEnEdicion(null)}
        onQuitar={(id) => {
          parchar({ lineas: activo?.lineas.filter((x) => x.id !== id) ?? [] });
          setLineaEnEdicion(null);
        }}
        onGuardar={guardarLinea}
        onAnularLinea={(id) => {
          const linea = activo?.lineas.find((x) => x.id === id);
          setLineaEnEdicion(null);
          if (linea) setLineaAQuitar({ id, nombre: linea.nombre });
        }}
      />
      <DialogoMotivoAnulacion
        linea={lineaAQuitar}
        ocupado={ocupado}
        onCerrar={() => setLineaAQuitar(null)}
        onConfirmar={(motivo) => {
          const id = lineaAQuitar?.id;
          setLineaAQuitar(null);
          if (id) void anularLineaEnviada(id, motivo);
        }}
      />
      <DespachoEnPdv
        sucursalId={sucursalId}
        abierto={viendoDespacho}
        onCerrar={() => setViendoDespacho(false)}
      />
      <DialogoDescuento
        abierto={dialogo === "descuento"}
        borrador={activo}
        ocupado={ocupado}
        onCerrar={() => setDialogo(null)}
        onCupon={canjearCupon}
        onDescuento={aplicarDescuento}
        onQuitarDescuento={quitarDescuento}
      />
      <DialogoTipo
        abierto={dialogo === "tipo"}
        borrador={activo}
        mesas={datos.mesas.datos}
        sucursalId={sucursalId}
        onCerrar={() => setDialogo(null)}
        onConfirmar={(cambios) => {
          // La nota de servicio se puede cambiar con la orden ya en cocina,
          // que es cuando de verdad se pide: si el pedido existe, viaja al
          // servidor además de quedar en el borrador.
          //
          // Se manda **siempre** que haya orden, sin comparar contra lo que
          // el borrador dice tener. Comparar parecía el ahorro obvio y es la
          // forma de que una desincronización sea permanente: basta que un
          // envío falle una vez para que el borrador local ya "tenga" la
          // nota y no se vuelva a intentar nunca. Es un PUT en un diálogo
          // que se abre pocas veces por turno.
          if (activo?.ventaId && typeof cambios.notaCocina === "string") {
            void api
              .fijarNotaCocina(activo.ventaId, cambios.notaCocina || null)
              .catch((e) => notificar(mensajeDe(e, "No se pudo guardar la nota")));
          }
          parchar(cambios);
          setDialogo(null);
        }}
      />
      <DialogoMover
        abierto={dialogo === "mover"}
        borrador={activo}
        mesas={datos.mesas.datos}
        abiertas={datos.abiertas.datos}
        onCerrar={() => setDialogo(null)}
        onConfirmar={moverSeleccionados}
      />
      <DialogoConsumoPersonal
        abierto={dialogo === "consumo"}
        ocupado={ocupado}
        onCerrar={() => setDialogo(null)}
        onConfirmar={marcarConsumoPersonal}
      />
      <DialogoCliente
        abierto={dialogo === "cliente"}
        permisos={permisos}
        onCerrar={() => setDialogo(null)}
        onBuscar={api.buscarClientes}
        onElegir={(c: ClienteBuscado) => {
          // El texto y su ancla viajan juntos: nunca uno sin el otro
          // (ADR-053), o el reparto cotizaría contra un punto ajeno al
          // texto que se ve en pantalla.
          parchar({ cliente: c, direccion: c.direccion, ubicacion: c });
          setDialogo(null);
        }}
        onCrear={crearCliente}
      />
      <DialogoCobro
        abierto={dialogo === "cobro"}
        permisos={permisos}
        total={totalDelCobro(saldoServidor, activo, seleccion)}
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
        <PieCobrado
          venta={cobradoAVer}
          ocupado={ocupado}
          onImprimir={impresion.imprimirComprobante}
        />
      </Dialogo>
      {impresion.hoja}
    </main>
  );
}

/** El receptor viaja con el pago que cierra la cuenta: es ese el que
 * dispara la emisión del comprobante. `grupoCobro` es 1 salvo que se esté
 * cobrando una cuenta separada (RN-COM-018). */
async function registrarPagos(
  ventaId: string,
  pagos: Array<{ medioId: string; monto: number }>,
  doc: string,
  nombre: string,
  grupoCobro: number,
  gravadoIgv: boolean | null,
) {
  for (const [i, p] of pagos.entries()) {
    const ultimo = i === pagos.length - 1;
    await api.registrarPago(ventaId, {
      medio_pago_id: p.medioId,
      // A dos decimales SIEMPRE. La aritmética del diálogo se hace en el
      // `number` de JS, y `String(23.299999999999997)` viajaba tal cual: el
      // pago entraba, pero nunca llegaba a cubrir el total, así que la venta
      // se quedaba en `orden` y sin comprobante.
      monto: p.monto.toFixed(2),
      idempotency_key: claveIdempotencia("pago"),
      grupo_cobro: grupoCobro,
      receptor_num_doc: ultimo ? doc || null : null,
      receptor_nombre: ultimo ? nombre || null : null,
      // Solo con el último: es el que cierra la cuenta y emite el
      // comprobante, igual que el receptor.
      gravado_igv: ultimo ? gravadoIgv : null,
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
    valores: [],
    grupoCobro: 1,
    // Recién marcada en la carta: existe solo en esta pantalla hasta que
    // alguien toque "Enviar" (ADR-075).
    enviada: false,
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
    nota: item.nota ?? "",
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
    // Ídem para los valores de atributo: `VentaItemOut` no los devuelve, así
    // que reabrir una línea ya enviada no puede recuperarlos. Con RN-COM-040
    // eso ahora es un 409 explícito al reenviarla —falla ruidosa— en vez de
    // una venta que se cobra sin descontar. Anotado como deuda.
    valores: [],
    grupoCobro: item.grupo_cobro,
    // Viene del servidor: ya está en la cola de cocina.
    enviada: true,
  };
}

function alternar(seleccion: Set<string>, id: string): Set<string> {
  const s = new Set(seleccion);
  if (s.has(id)) s.delete(id);
  else s.add(id);
  return s;
}

/**
 * Lo que el diálogo de cobro tiene que mostrar.
 *
 * Manda el saldo del servidor cuando se lo pudo pedir. El total del borrador
 * es el respaldo: sirve para el pedido que todavía no se envió —no hay venta
 * contra la que preguntar— y para cuando la consulta falla.
 */
function totalDelCobro(
  saldo: number | null,
  activo: Borrador | null,
  seleccion: Set<string>,
): number {
  return saldo ?? totalACobrar(activo, seleccion);
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

/** Pie del diálogo de una cuenta cobrada. Componente aparte y no un bloque
 * más dentro de `PdvCliente`: la pantalla ya carga con quince
 * responsabilidades y el linter corta la complejidad en diez. */
function PieCobrado({
  venta,
  ocupado,
  onImprimir,
}: {
  venta: Venta | null;
  ocupado: boolean;
  onImprimir: (venta: Venta, comprobanteId?: string) => void;
}) {
  // Una venta dividida tiene un comprobante por cuenta (RN-COM-018). Antes
  // el pie ofrecía un solo botón que imprimía el primero, así que el
  // segundo cliente se quedaba sin su papel — que es exactamente para lo
  // que se había separado la cuenta.
  const [comprobantes, setComprobantes] = useState<ComprobanteDeVenta[]>([]);
  useEffect(() => {
    if (!venta) return setComprobantes([]);
    let vigente = true;
    api
      .comprobantesDeVenta(venta.id)
      .then((cs) => vigente && setComprobantes(cs))
      // Sin la lista queda el botón único, que es lo que había antes: se
      // imprime el primero en vez de no imprimir nada.
      .catch(() => vigente && setComprobantes([]));
    return () => {
      vigente = false;
    };
  }, [venta]);

  if (!venta) return null;
  return (
    <footer className="pdv-dialogo-pie">
      {comprobantes.length > 1 ? (
        comprobantes.map((c) => (
          <button
            key={c.id}
            type="button"
            className="pdv-boton-pri"
            disabled={ocupado}
            onClick={() => onImprimir(venta, c.id)}
          >
            {`Cuenta ${c.grupo_cobro} · ${c.serie}-${c.correlativo}`}
          </button>
        ))
      ) : (
        <button
          type="button"
          className="pdv-boton-pri"
          disabled={ocupado}
          onClick={() => onImprimir(venta, comprobantes[0]?.id)}
        >
          Imprimir comprobante
        </button>
      )}
    </footer>
  );
}
