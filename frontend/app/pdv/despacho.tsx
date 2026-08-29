"use client";

import { useEffect, useRef, useState } from "react";

import { apiKds, SEMAFORO_DE_FABRICA, type Pantalla, type Semaforo } from "@/lib/kds";

import DespachoCliente from "../kds/despacho-cliente";
import "../kds/kds.css";

/**
 * La pantalla de despacho, **dentro** del PDV.
 *
 * El personal la pidió así: hoy la cola de despacho vive en otra pantalla
 * del local y hay que caminar hasta ella para saber si un pedido ya salió.
 * Desde la misma tablet donde se toma la orden, ese viaje desaparece.
 *
 * Es un overlay y no una navegación a propósito: salir del PDV cierra la
 * caja de la vista y descarta el pedido a medio armar de la pantalla. El
 * turno no puede perder de vista lo que está cobrando para mirar la cola.
 *
 * Reusa `DespachoCliente` tal cual —misma cola, mismo polling, mismo botón
 * de entregar— en vez de dibujar una versión reducida: una segunda vista de
 * la misma cola es una segunda vista que se desincroniza.
 */
export default function DespachoEnPdv({
  sucursalId,
  abierto,
  onCerrar,
}: {
  sucursalId: string;
  abierto: boolean;
  onCerrar: () => void;
}) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const [pantalla, setPantalla] = useState<Pantalla | null>(null);
  const [semaforo, setSemaforo] = useState<Semaforo>(SEMAFORO_DE_FABRICA);
  const [falla, setFalla] = useState<string | null>(null);

  // Se resuelve al abrir y no al montar: es una pantalla que la mayoría de
  // los turnos no toca, y pedir su configuración en cada arranque del PDV
  // serían dos llamadas más para nada.
  useEffect(() => {
    if (!abierto) return;
    let vigente = true;
    apiKds
      .pantallas(sucursalId)
      .then((todas) => {
        if (!vigente) return;
        const despacho = todas.find((p) => p.tipo === "despacho" && p.activo);
        setPantalla(despacho ?? null);
        setFalla(
          despacho
            ? null
            : "Esta sucursal no tiene pantalla de despacho. Se da de alta en Cocina → Estaciones.",
        );
      })
      .catch(() => {
        if (vigente) setFalla("No se pudo cargar la cola de despacho.");
      });
    apiKds
      .configuracion(sucursalId)
      .then((s) => vigente && setSemaforo(s))
      .catch(() => {
        // Colores de fábrica: es un semáforo, no un dato del pedido.
      });
    return () => {
      vigente = false;
    };
  }, [abierto, sucursalId]);

  useEffect(() => {
    const d = dialogo.current;
    if (!d) return;
    // `showModal()` y no un `div` con z-index: el PDV usa diálogos nativos y
    // solo el top layer del navegador queda por encima de ellos.
    if (abierto && !d.open) d.showModal();
    if (!abierto && d.open) d.close();
  }, [abierto]);

  return (
    <dialog
      ref={dialogo}
      className="pdv-despacho"
      aria-label="Despacho"
      onClose={onCerrar}
    >
      <button
        type="button"
        className="pdv-despacho-cerrar"
        onClick={onCerrar}
        aria-label="Cerrar despacho"
      >
        ×
      </button>
      {pantalla ? (
        <DespachoCliente
          pantalla={{ id: pantalla.id, nombre: pantalla.nombre }}
          sucursalId={sucursalId}
          // Entregar desde acá es el punto: el que cobra es el que ve salir
          // el pedido. El permiso real lo valida la API en cada request.
          puedeEntregar
          semaforo={semaforo}
          // Sin los enlaces a Historial y Estaciones: son navegaciones fuera
          // del PDV, y desde un overlay eso es una trampa.
          sinNavegacion
        />
      ) : (
        <main className="kds-vacio">
          <h1>Despacho</h1>
          <p>{falla ?? "Cargando la cola…"}</p>
        </main>
      )}
    </dialog>
  );
}
