/** Aritmética del cobro del PDV, fuera del JSX: mezclarla con el diálogo es
 * lo que hacía ilegible cuánto pesaba cada rama, y deja probable sin
 * navegador lo único que decide cuánta plata entra. */
import type { MedioPago } from "./pdv";

export type PagoParcial = { medioId: string; monto: number };

export function calcularCobro(
  total: number,
  pagos: PagoParcial[],
  monto: string,
  medioId: string,
  medios: MedioPago[],
) {
  const confirmado = pagos.reduce((a, p) => a + p.monto, 0);
  const enCurso = Math.max(0, Number(monto) || 0);
  const falta = Math.max(0, total - confirmado);
  // El vuelto solo existe en efectivo: en tarjeta o Yape no hay cajón que
  // devuelva plata, así que ahí un monto de más es un error de tecleo, no
  // un cobro válido (se bloquea en vez de registrarse).
  const esEfectivo = medios.find((m) => m.id === medioId)?.tipo === "efectivo";
  const excede = enCurso > falta && !esEfectivo;
  // Lo que realmente se le acredita a la venta nunca pasa del saldo — el
  // backend lo rechazaría igual (RN-COM-002) — el resto es vuelto físico,
  // no un pago de más.
  const aplicado = Math.min(enCurso, falta);
  const pagado = confirmado + aplicado;
  return {
    enCurso,
    falta,
    excede,
    aplicado,
    pagado,
    restante: Math.max(0, total - pagado),
    vuelto: esEfectivo ? Math.max(0, enCurso - falta) : 0,
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
  return ocupado || excede || pagado < total || !docValido || !medioId;
}
