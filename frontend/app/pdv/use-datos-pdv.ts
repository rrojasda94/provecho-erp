"use client";

import { useCallback, useEffect, useState } from "react";

import {
  api,
  type CajaAbierta,
  type ItemDeCarta,
  type MedioPago,
  type MesaEnMapa,
  type Venta,
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
export function useDatosPdv(empresaId: string | null, puntoVentaId: string, sucursalId: string) {
  const [caja, setCaja] = useState<CajaAbierta | null>(null);
  const [cajaResuelta, setCajaResuelta] = useState(false);
  const [carta, setCarta] = useState<ItemDeCarta[]>([]);
  const [medios, setMedios] = useState<MedioPago[]>([]);
  const [mesas, setMesas] = useState<MesaEnMapa[]>([]);
  const [cobrados, setCobrados] = useState<Venta[]>([]);
  const [abiertas, setAbiertas] = useState<Venta[]>([]);
  const [modalidad, setModalidad] = useState("mesa");

  useEffect(() => {
    if (!empresaId) {
      setCajaResuelta(true);
      return;
    }
    api
      .cajasAbiertas(empresaId)
      .then((abiertas) =>
        setCaja(abiertas.find((c) => c.punto_venta_id === puntoVentaId) ?? null),
      )
      .catch(() => setCaja(null))
      .finally(() => setCajaResuelta(true));
  }, [empresaId, puntoVentaId]);

  const recargarMesas = useCallback(() => {
    api.mapaMesas(sucursalId).then(setMesas).catch(() => setMesas([]));
  }, [sucursalId]);

  const recargarCobrados = useCallback(() => {
    api
      .ventasDelDia(sucursalId, "pagada")
      .then(setCobrados)
      .catch(() => setCobrados([]));
  }, [sucursalId]);

  // Pedidos ya enviados a cocina pero sin cobrar: para llevar/delivery no
  // se ven en el mapa de mesas, y sin esto se pierden si se recarga la
  // página antes de cobrarlos.
  const recargarAbiertas = useCallback(() => {
    api
      .ventasDelDia(sucursalId, "orden")
      .then((vs) => setAbiertas(vs.filter((v) => !v.mesa_id)))
      .catch(() => setAbiertas([]));
  }, [sucursalId]);

  useEffect(() => {
    if (!caja) return;
    // El precio depende de la modalidad (RN-PRC-003): la carta se vuelve a
    // pedir al cambiar entre mesa, para llevar y delivery.
    api.carta(sucursalId, modalidad).then(setCarta).catch(() => setCarta([]));
  }, [caja, sucursalId, modalidad]);

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
    cajaResuelta,
    carta,
    medios,
    mesas,
    cobrados,
    abiertas,
    setModalidad,
    recargarMesas,
    recargarCobrados,
    recargarAbiertas,
  };
}
