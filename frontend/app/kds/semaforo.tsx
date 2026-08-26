"use client";

import {
  minutosDesde,
  nivelDe,
  reloj,
  type Nivel,
  type PedidoCola,
  type Semaforo,
} from "@/lib/kds";

/**
 * El tiempo de espera en la tarjeta, y el color que le corresponde.
 *
 * Hasta ahora la cocina no tenía ninguna noción de tiempo: un pedido de hace
 * cuarenta minutos se veía igual que uno recién tomado. Los umbrales y los
 * colores los fija Gerencia (`kds_semaforo.py`) porque ocho minutos son una
 * eternidad en una barra de bebidas y nada en un horno a leña.
 *
 * No hay `setInterval`: el reloj avanza con el refresco de la cola, que ya
 * corre cada 3 s y devuelve un array nuevo. Un temporizador propio sería un
 * segundo re-render por el mismo minuto.
 */

/** Un pedido ya listo se pinta verde aunque lleve una hora: lo que el color
 * comunica es "esto necesita atención", y uno listo espera al que despacha,
 * no a la cocina. */
export function nivelDelPedido(pedido: PedidoCola, semaforo: Semaforo): Nivel {
  if (pedido.estado_pedido === "listo" || pedido.estado_pedido === "entregado") {
    return "normal";
  }
  return nivelDe(minutosDesde(pedido.creado_en), semaforo);
}

export function Espera({ pedido, semaforo }: { pedido: PedidoCola; semaforo: Semaforo }) {
  const minutos = minutosDesde(pedido.creado_en);
  return (
    <span className={`kds-espera ${nivelDelPedido(pedido, semaforo)}`}>
      {reloj(minutos)}
    </span>
  );
}

/** Los colores de Gerencia como variables CSS sobre la raíz de la pantalla.
 * Van inline y no en la hoja porque son datos, no diseño: cambiarlos no
 * puede pedir un despliegue. */
export function coloresDe(semaforo: Semaforo): React.CSSProperties {
  return {
    "--kds-normal": semaforo.color_normal,
    "--kds-ambar": semaforo.color_ambar,
    "--kds-rojo": semaforo.color_rojo,
  } as React.CSSProperties;
}
