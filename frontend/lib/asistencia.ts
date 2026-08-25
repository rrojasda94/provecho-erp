/**
 * Cliente y tipos del pad de marcación de asistencia. Espeja los esquemas
 * `TarjetaOut` / `PadMarcarIn` de `rrhh/api/schemas.py`.
 *
 * La tarjeta trae el nombre y nada más: la pantalla está a la vista de todo
 * el que pase por la cocina. Y el cliente no elige si marca entrada o
 * salida — lo decide el servidor con el estado del día (ADR-064).
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

export const apiAsistencia = {
  tarjetas: (sucursalId: string) =>
    pedir<Tarjeta[]>(
      `/rrhh/asistencia/terminal/tarjetas?sucursal_id=${sucursalId}`,
    ),

  marcar: (sucursalId: string, trabajadorId: string, pin: string) =>
    pedir<Marcacion>(
      `/rrhh/asistencia/terminal/marcar?sucursal_id=${sucursalId}`,
      { metodo: "POST", cuerpo: { trabajador_id: trabajadorId, pin } },
    ),
};
