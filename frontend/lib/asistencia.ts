/**
 * Cliente y tipos del pad de marcación de asistencia. Espeja los esquemas
 * `TarjetaOut` / `PadMarcarIn` de `rrhh/api/schemas.py`.
 *
 * La tarjeta trae el nombre y nada más: la pantalla está a la vista de todo
 * el que pase por la cocina. Y el cliente no elige si marca entrada o
 * salida — lo decide el servidor con el estado del día (ADR-065).
 */

import { pedir } from "./cliente-api";

export type Tarjeta = {
  trabajador_id: string;
  nombre: string;
  marco_entrada: boolean;
  marco_salida: boolean;
};

export type Marcacion = {
  tipo: "entrada" | "salida";
  asistencia: {
    fecha: string;
    hora_entrada: string | null;
    hora_salida: string | null;
    tardanza_min: number;
  };
};

/** Evidencia opcional del marcaje (RN-RRHH-024, ADR-073): ninguno de los
 * tres es obligatorio, y su ausencia nunca impide marcar. `foto` va en
 * base64 sin el encabezado `data:image/jpeg;base64,`. */
export type EvidenciaMarcaje = {
  foto?: string;
  lat?: number;
  lng?: number;
};

export const apiAsistencia = {
  tarjetas: (sucursalId: string) =>
    pedir<Tarjeta[]>(
      `/rrhh/asistencia/terminal/tarjetas?sucursal_id=${sucursalId}`,
    ),

  marcar: (
    sucursalId: string,
    trabajadorId: string,
    pin: string,
    evidencia: EvidenciaMarcaje = {},
  ) =>
    pedir<Marcacion>(
      `/rrhh/asistencia/terminal/marcar?sucursal_id=${sucursalId}`,
      {
        metodo: "POST",
        cuerpo: { trabajador_id: trabajadorId, pin, ...evidencia },
      },
    ),

  /** El código de 6 dígitos que un admin generó desde el back-office. La
   * tablet lo teclea una sola vez; el secreto que devuelve lo guarda
   * `activarTerminalAction` en la cookie, nunca este cliente. */
  enrolarTerminal: (sucursalId: string, codigo: string) =>
    pedir<{ secreto: string }>(
      `/rrhh/asistencia/terminal/enrolar?sucursal_id=${sucursalId}`,
      { metodo: "POST", cuerpo: { codigo } },
    ),
};
