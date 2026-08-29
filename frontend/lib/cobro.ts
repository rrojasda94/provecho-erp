/** Aritmética del cobro del PDV, fuera del JSX: mezclarla con el diálogo es
 * lo que hacía ilegible cuánto pesaba cada rama, y deja probable sin
 * navegador lo único que decide cuánta plata entra. */
import type { MedioPago } from "./pdv";

export type PagoParcial = { medioId: string; monto: number };

/**
 * A centavos, que es lo único que existe en una caja.
 *
 * La aritmética del cobro se hace en el `number` de JS, así que una resta
 * tan inocente como 33.30 − 10 deja 23.299999999999997. Ese sobrante
 * invisible viajaba tal cual al servidor —`String(monto)`— y hacía que la
 * suma de los pagos nunca llegara al total: el cajero cobraba, la venta se
 * quedaba en `orden` y no se emitía comprobante. En el otro sentido, un
 * `pagado < total` por una millonésima deshabilitaba "Confirmar pago" con
 * "Restante S/ 0.00" en pantalla.
 *
 * `Math.round` sobre centavos y no `toFixed`: acá hace falta el número para
 * seguir operando, y el string solo al final.
 */
export function aCentavos(monto: number): number {
  return Math.round((monto + Number.EPSILON) * 100) / 100;
}

export function calcularCobro(
  total: number,
  pagos: PagoParcial[],
  monto: string,
  medioId: string,
  medios: MedioPago[],
) {
  const confirmado = aCentavos(pagos.reduce((a, p) => a + p.monto, 0));
  const enCurso = aCentavos(Math.max(0, Number(monto) || 0));
  const falta = aCentavos(Math.max(0, total - confirmado));
  // El vuelto solo existe en efectivo: en tarjeta o Yape no hay cajón que
  // devuelva plata, así que ahí un monto de más es un error de tecleo, no
  // un cobro válido (se bloquea en vez de registrarse).
  const esEfectivo = medios.find((m) => m.id === medioId)?.tipo === "efectivo";
  const excede = enCurso > falta && !esEfectivo;
  // Lo que realmente se le acredita a la venta nunca pasa del saldo — el
  // backend lo rechazaría igual (RN-COM-002) — el resto es vuelto físico,
  // no un pago de más.
  const aplicado = aCentavos(Math.min(enCurso, falta));
  const pagado = aCentavos(confirmado + aplicado);
  return {
    enCurso,
    falta,
    excede,
    aplicado,
    pagado,
    restante: aCentavos(Math.max(0, total - pagado)),
    vuelto: esEfectivo ? aCentavos(Math.max(0, enCurso - falta)) : 0,
  };
}

/** `medioId` vacío bloquea: sin medios de pago en el catálogo no hay
 * ninguno seleccionado, y confirmar mandaba `medio_pago_id: ""` — el
 * backend respondía «Input should be a valid UUID», que en la pantalla del
 * cajero no significa nada y no se puede corregir desde ahí. */
export function cobroBloqueado(
  ocupado: boolean,
  excede: boolean,
  pagado: number,
  total: number,
  docValido: boolean,
  medioId: string,
): boolean {
  // A centavos en los dos lados: comparar los `number` crudos dejaba el
  // botón muerto cuando la suma de los parciales daba 58.699999999999996
  // por un total de 58.70.
  return (
    ocupado ||
    excede ||
    aCentavos(pagado) < aCentavos(total) ||
    !docValido ||
    !medioId
  );
}
