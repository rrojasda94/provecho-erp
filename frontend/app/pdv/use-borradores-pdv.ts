"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/pdv";

import type { Borrador } from "./tipos";

/**
 * El ticket a medio armar, guardado contra el servidor (ADR-074).
 *
 * Hasta ahora los borradores vivían **solo** en `useState`: recargar la
 * página, quedarse sin batería o cambiar de turno borraba las pestañas de
 * pedido y el mesero volvía a teclear la mesa entera.
 *
 * Se guardan contra el **punto de venta** y no contra el usuario: el relevo
 * de turno tiene que poder seguir el pedido que dejó el anterior sin que ese
 * cierre sesión primero.
 *
 * Nada de esto bloquea la caja. Si el guardado falla —red intermitente, API
 * caída—, el PDV sigue vendiendo con el borrador en memoria, que es
 * exactamente lo que hacía antes: la persistencia es una red de seguridad,
 * no un requisito para tomar un pedido.
 */

/** Lo que se espera entre la última tecla y el guardado. Suficiente para no
 * mandar un PUT por cada dígito de una cantidad, y corto frente a lo que
 * tarda alguien en levantarse de la caja. */
const ESPERA_GUARDADO_MS = 800;

/** Un borrador que no vale la pena guardar: sin líneas, sin destino y sin
 * haber salido a cocina, es la pestaña en blanco con la que el PDV arranca.
 * Guardarla llenaría la tabla de tickets vacíos y devolvería pestañas
 * fantasma en cada arranque. */
function valeLaPena(b: Borrador): boolean {
  return (
    b.lineas.length > 0 || Boolean(b.ventaId) || Boolean(b.mesaId) || Boolean(b.cliente)
  );
}

export function useBorradoresPdv(
  puntoVentaId: string,
  borradores: Borrador[],
  restaurar: (guardados: Borrador[]) => void,
) {
  const [cargado, setCargado] = useState(false);
  // `restaurar` viene del componente y cambia en cada render; guardarla en
  // una ref deja al efecto de carga con dependencias estables — si no, la
  // carga inicial se dispararía otra vez con cada tecla. Se asigna en un
  // efecto y no durante el render: escribir una ref mientras se renderiza es
  // lo que rompe con `<StrictMode>` y con el compilador de React.
  const restaurarRef = useRef(restaurar);
  useEffect(() => {
    restaurarRef.current = restaurar;
  });
  /** Lo último que se mandó de cada pestaña. Sin esto, cualquier cambio en
   * una pestaña reenviaría también las otras, sin haber cambiado. */
  const guardado = useRef(new Map<string, string>());

  useEffect(() => {
    let vigente = true;
    api
      .borradores(puntoVentaId)
      .then((filas) => {
        if (!vigente) return;
        const recuperados = filas.map((f) => f.contenido as Borrador);
        for (const b of recuperados) {
          guardado.current.set(b.id, JSON.stringify(b));
        }
        if (recuperados.length) restaurarRef.current(recuperados);
      })
      .catch(() => {
        // Sin borradores recuperados se arranca en blanco, que es como
        // arrancaba antes de ADR-074.
      })
      .finally(() => {
        if (vigente) setCargado(true);
      });
    return () => {
      vigente = false;
    };
  }, [puntoVentaId]);

  useEffect(() => {
    // Antes de terminar la carga no se guarda nada: se estaría pisando lo
    // que está por llegar con la pestaña en blanco del arranque.
    if (!cargado) return;
    const t = setTimeout(() => {
      for (const b of borradores) {
        if (!valeLaPena(b)) continue;
        const serializado = JSON.stringify(b);
        if (guardado.current.get(b.id) === serializado) continue;
        guardado.current.set(b.id, serializado);
        api.guardarBorrador(b.id, puntoVentaId, b).catch(() => {
          // Se olvida lo anotado para que el próximo cambio lo reintente.
          guardado.current.delete(b.id);
        });
      }
    }, ESPERA_GUARDADO_MS);
    return () => clearTimeout(t);
  }, [borradores, cargado, puntoVentaId]);

  /** Borra el borrador del servidor. Se llama al cerrar la pestaña y al
   * cobrar: desde ahí el pedido es una `venta` y ya no hay nada a medio
   * armar que recuperar. */
  const descartar = useCallback((borradorId: string) => {
    guardado.current.delete(borradorId);
    api.descartarBorrador(borradorId).catch(() => {
      // Idempotente del lado del servidor y filtrado por jornada del lado
      // del listado: un descarte perdido desaparece solo mañana.
    });
  }, []);

  return { cargado, descartar };
}
