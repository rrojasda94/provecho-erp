"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorApi } from "@/lib/cliente-api";
import { apiKds, type PedidoCola } from "@/lib/kds";

/**
 * Cada cuánto se relee la cola. El estado real vive en el backend
 * (`venta_item.estado_preparacion` + `etapa_kds`), así que este intervalo es
 * lo que tarda una pantalla en enterarse de lo que hizo otra: 3 s es
 * imperceptible en cocina y son ~20 requests/minuto por tablet, nada para
 * esta API. El push en vivo (WebSocket/Redis) es deuda declarada en
 * `ROADMAP.md`.
 */
const REFRESCO_MS = 3000;

/**
 * Cola de una pantalla con su sondeo. Vive aparte porque preparación y
 * despacho muestran cosas distintas del mismo dato: sin esto, el pausado
 * por pestaña oculta y el refresco al volver estarían escritos dos veces y
 * se irían separando.
 */
export function useCola(pantallaId: string) {
  const [pedidos, setPedidos] = useState<PedidoCola[]>([]);
  const [aviso, setAviso] = useState<string | null>(null);
  const [cargado, setCargado] = useState(false);

  const refrescar = useCallback(async () => {
    try {
      setPedidos(await apiKds.cola(pantallaId));
    } catch (e) {
      setAviso(e instanceof ErrorApi ? e.message : "Sin conexión con la API");
    } finally {
      setCargado(true);
    }
  }, [pantallaId]);

  useEffect(() => {
    refrescar();
    const id = setInterval(() => {
      // Tablet con la pantalla apagada o el navegador en otra pestaña: no
      // tiene sentido seguir pidiendo la cola.
      if (!document.hidden) refrescar();
    }, REFRESCO_MS);
    // Al volver a mirar la pantalla, la cola puede llevar horas congelada:
    // esperar al siguiente tick mostraría pedidos viejos durante 3 s.
    const alVolver = () => {
      if (!document.hidden) refrescar();
    };
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", alVolver);
    };
  }, [refrescar]);

  useEffect(() => {
    if (!aviso) return;
    const id = setTimeout(() => setAviso(null), 4000);
    return () => clearTimeout(id);
  }, [aviso]);

  const avisarDe = (e: unknown, porDefecto: string) =>
    setAviso(e instanceof ErrorApi ? e.message : porDefecto);

  return { pedidos, setPedidos, aviso, setAviso, avisarDe, cargado, refrescar };
}
