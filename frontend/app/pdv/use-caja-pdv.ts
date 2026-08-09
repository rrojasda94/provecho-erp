"use client";

import {
  api,
  soles,
  type CajaAbierta,
  type CustodiaDestino,
  type DescuadreAtribucion,
  type PosVerificadoNuevo,
} from "@/lib/pdv";

export type DatosApertura = {
  montoDeclarado: number;
  detalle: Record<string, number>;
  posVerificados: PosVerificadoNuevo[];
  encargado: { username: string; pin: string };
};

export type DatosCierre = {
  detalle: Record<string, number>;
  custodia: CustodiaDestino;
  /** `""` = sin atribuir todavía, que es un caso legítimo: un descuadre se
   * investiga después. Viaja como `null`. */
  atribucion: DescuadreAtribucion | "";
  reportesPos: { pos_tarjeta_id: string; monto_lote: string; referencia?: string }[];
  receptor: { username: string; pin: string };
};

/**
 * Apertura y cierre del turno desde el PDV (ADR-025).
 *
 * Vive fuera de `PdvCliente` porque el ciclo de caja no es parte de vender:
 * es un traspaso de custodia entre dos personas que se firma con PIN, y
 * tenerlo dentro del componente lo empujaba sobre el límite de complejidad
 * que el proyecto se puso.
 *
 * El PIN nunca se guarda: se cambia por una elevación acotada al permiso
 * (`accounting.caja_relevar`) y lo que viaja al servidor es ese token, del
 * que el backend saca quién firmó. Mandar el id del encargado sería una
 * firma que cualquiera puede escribir.
 */
export function useCajaPdv({
  puntoVentaId,
  caja,
  setCaja,
  setOcupado,
  notificar,
  mensajeDe,
  alCerrarTurno,
}: {
  puntoVentaId: string;
  caja: CajaAbierta | null;
  setCaja: (caja: CajaAbierta | null) => void;
  setOcupado: (ocupado: boolean) => void;
  notificar: (texto: string) => void;
  mensajeDe: (e: unknown, porDefecto: string) => string;
  /** Se llama solo si el cierre entró: un cierre rechazado tiene que dejar
   * el diálogo abierto con lo tecleado, o el cajero recuenta todo de nuevo. */
  alCerrarTurno: () => void;
}) {
  const abrirCaja = async (datos: DatosApertura) => {
    setOcupado(true);
    try {
      const elevacion = await api.autorizar(
        datos.encargado.username,
        datos.encargado.pin,
        "accounting.caja_relevar",
      );
      const abierta = await api.abrirCaja({
        punto_venta_id: puntoVentaId,
        autorizacion: elevacion.autorizacion,
        // El monto de apertura sale del conteo, no de esto: lo declarado es
        // contra qué se contrasta (RN-POS-003/011).
        monto_declarado: String(datos.montoDeclarado),
        detalle_denominaciones: datos.detalle,
        pos_verificados: datos.posVerificados,
      });
      setCaja(abierta);
      notificar(`Caja abierta con ${soles(abierta.monto_apertura)}`);
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo abrir la caja"));
    } finally {
      setOcupado(false);
    }
  };

  const cerrarCaja = async (datos: DatosCierre): Promise<void> => {
    if (!caja) return;
    setOcupado(true);
    try {
      const elevacion = await api.autorizar(
        datos.receptor.username,
        datos.receptor.pin,
        "accounting.caja_relevar",
      );
      const cierre = await api.cerrarCaja(caja.apertura_caja_id, {
        detalle_denominaciones: datos.detalle,
        custodia: datos.custodia,
        autorizacion: elevacion.autorizacion,
        descuadre_atribucion: datos.atribucion === "" ? null : datos.atribucion,
        reportes_pos: datos.reportesPos,
      });
      setCaja(null);
      alCerrarTurno();
      notificar(
        cierre.estado === "conforme"
          ? "Caja cerrada: conforme"
          : `Caja cerrada con descuadre de ${soles(cierre.descuadre_monto)}`,
      );
    } catch (e) {
      notificar(mensajeDe(e, "No se pudo cerrar la caja"));
    } finally {
      setOcupado(false);
    }
  };

  // Los terminales que este turno dio por operativos: es a esos, y solo a
  // esos, a los que el cierre les va a pedir su reporte de lote.
  return { abrirCaja, cerrarCaja, posDelTurno: caja?.pos_verificados ?? [] };
}
