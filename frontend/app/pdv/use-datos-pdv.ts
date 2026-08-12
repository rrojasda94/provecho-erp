"use client";

import { useCallback, useEffect, useState } from "react";

import { fallaDe, type Falla, type Lista } from "@/lib/carga";
import {
  api,
  type CajaAbierta,
  type ItemDeCarta,
  type MedioPago,
  type PosTarjeta,
} from "@/lib/pdv";

/**
 * Todo lo que el PDV lee del servidor, en un solo lugar.
 *
 * Vive fuera del componente para que la pantalla se ocupe de la interacción
 * y no de orquestar cinco cargas: mezclarlas ahí hacía que cualquier cambio
 * de UI tuviera que leerse entre `useEffect`.
 *
 * Nada se carga antes de tener caja abierta: sin caja no se puede vender, y
 * pedir la carta solo para dejarla detrás de un modal es trabajo perdido.
 *
 * El nombre arranca en inglés (`use...`) porque React exige ese prefijo para
 * reconocerlo como hook y aplicarle sus reglas; es restricción del
 * framework, no una excepción al idioma del proyecto.
 */
export function useDatosPdv(puntoVentaId: string, sucursalId: string) {
  const [caja, setCaja] = useState<CajaAbierta | null>(null);
  const [fallaCaja, setFallaCaja] = useState<Falla | null>(null);
  const [cajaResuelta, setCajaResuelta] = useState(false);
  const [carta, setCarta] = useState<ItemDeCarta[]>([]);
  const [medios, setMedios] = useState<MedioPago[]>([]);
  const [pos, setPos] = useState<PosTarjeta[]>([]);
  const [modalidad, setModalidad] = useState("mesa");

  const mesas = useLista(traerMesas, sucursalId, "No se pudo cargar el mapa de mesas");
  const cobrados = useLista(
    traerCobrados,
    sucursalId,
    "No se pudieron cargar los pedidos cobrados de hoy",
  );
  const abiertas = useLista(
    traerAbiertas,
    sucursalId,
    "No se pudieron cargar los pedidos en cocina",
  );

  // Fuera del `if (!caja)` del resto: los terminales se verifican **al
  // abrir** (RN-POS-010), así que tienen que estar cargados justo cuando
  // todavía no hay caja.
  useEffect(() => {
    api.posDeSucursal(sucursalId).then(setPos).catch(() => setPos([]));
  }, [sucursalId]);

  // La caja es del **punto de venta**, no del usuario: si el turno ya lo
  // abrió otro cajero o un mesero del local, quien entra después sigue
  // trabajando sobre esa caja y no tiene nada que abrir.
  //
  // El fallo NO se puede tratar como "no hay caja": eso convertía un 403 en
  // el diálogo de apertura, y la apertura después rebotaba con "ya hay una
  // caja abierta" — un callejón sin salida donde el cajero no puede ni
  // vender ni entender por qué. Es el mismo motivo por el que `useLista`
  // guarda su falla; acá faltaba.
  useEffect(() => {
    api
      .cajasAbiertas(sucursalId)
      .then((deLaSucursal) => {
        setCaja(deLaSucursal.find((c) => c.punto_venta_id === puntoVentaId) ?? null);
        setFallaCaja(null);
      })
      .catch((e) => {
        setCaja(null);
        setFallaCaja(fallaDe(e, "No se pudo saber si la caja está abierta"));
      })
      .finally(() => setCajaResuelta(true));
  }, [sucursalId, puntoVentaId]);

  useEffect(() => {
    if (!caja) return;
    // El precio depende de la modalidad (RN-PRC-003): la carta se vuelve a
    // pedir al cambiar entre mesa, para llevar y delivery.
    api.carta(sucursalId, modalidad).then(setCarta).catch(() => setCarta([]));
  }, [caja, sucursalId, modalidad]);

  // Sacadas del objeto para que `exhaustive-deps` pueda verlas: pedir
  // `mesas` entero en las dependencias reejecutaría el efecto con cada fila
  // que llega.
  const { recargar: recargarMesas } = mesas;
  const { recargar: recargarCobrados } = cobrados;
  const { recargar: recargarAbiertas } = abiertas;

  useEffect(() => {
    if (!caja) return;
    api.mediosPago().then(setMedios).catch(() => setMedios([]));
    recargarMesas();
    recargarCobrados();
    recargarAbiertas();
  }, [caja, recargarMesas, recargarCobrados, recargarAbiertas]);

  return {
    caja,
    setCaja,
    fallaCaja,
    cajaResuelta,
    carta,
    medios,
    mesas,
    cobrados,
    abiertas,
    pos,
    setModalidad,
  };
}

const traerMesas = (sucursalId: string) => api.mapaMesas(sucursalId);

const traerCobrados = (sucursalId: string) => api.ventasDelDia(sucursalId, "pagada");

/** Pedidos ya enviados a cocina pero sin cobrar: para llevar/delivery no se
 * ven en el mapa de mesas, y sin esto se pierden si se recarga la página
 * antes de cobrarlos. */
const traerAbiertas = async (sucursalId: string) =>
  (await api.ventasDelDia(sucursalId, "orden")).filter((v) => !v.mesa_id);

/**
 * Una lista del servidor que recuerda **por qué** no se pudo traer.
 *
 * Antes cada carga era `.catch(() => setLista([]))`: ni la pantalla ni el
 * cajero podían distinguir "hoy no se cobró nada" de "la petición se cayó".
 * Guardar la falla aparte deja el estado vacío para lo que de verdad está
 * vacío, y `recargar` es a la vez la carga inicial y el botón de reintento.
 *
 * Las filas viejas no se borran al fallar —la UI muestra la falla en su
 * lugar, no filas rancias—, pero así el mapa de mesas sigue sirviendo al
 * selector de mesa mientras el reintento va y vuelve.
 *
 * `cargar` se define a nivel de módulo justamente para que su identidad sea
 * estable y `recargar` no se recree en cada render.
 */
function useLista<T>(
  cargar: (sucursalId: string) => Promise<T[]>,
  sucursalId: string,
  mensaje: string,
): Lista<T> {
  const [datos, setDatos] = useState<T[]>([]);
  const [falla, setFalla] = useState<Falla | null>(null);

  const recargar = useCallback(() => {
    cargar(sucursalId)
      .then((filas) => {
        setDatos(filas);
        setFalla(null);
      })
      .catch((e) => setFalla(fallaDe(e, mensaje)));
  }, [cargar, sucursalId, mensaje]);

  return { datos, falla, recargar };
}
