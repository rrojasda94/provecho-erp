"use client";

import { useId } from "react";

/**
 * Teclado numérico para los PIN del PDV (ADR-045, RN-POS-014).
 *
 * No hay `<input>` en ninguna parte, y esa es la razón de existir del
 * componente: mientras el PIN se tecleaba en un `<input type="password">`,
 * el navegador ofrecía guardarlo y el turno siguiente entraba con la cuenta
 * del anterior. Un campo que el gestor de contraseñas no ve no se puede
 * guardar, y un PIN que no se guarda hay que saberlo.
 *
 * El valor vive en el estado de React; lo que se ve son puntos. Se acepta
 * el teclado físico (hay cajas con uno) porque el objetivo es que el
 * navegador no lo capture, no incomodar a quien opera.
 *
 * Vive en `app/pdv/` y no en `components/`: por decisión del encargo el
 * pinpad es solo del PDV. Si algún día lo pide otra pantalla, se muda.
 */

const TECLAS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];

type Props = {
  value: string;
  onChange: (pin: string) => void;
  /** Qué PIN se está pidiendo: "PIN del encargado", "Tu PIN"… */
  label: string;
  largo?: number;
  testid?: string;
  /** Se dispara al completar el largo — evita un toque extra en "Aceptar". */
  onCompleto?: (pin: string) => void;
};

export default function Pinpad({
  value,
  onChange,
  label,
  largo = 6,
  testid,
  onCompleto,
}: Props) {
  const idEstado = useId();

  const escribir = (digito: string) => {
    if (value.length >= largo) return;
    const nuevo = value + digito;
    onChange(nuevo);
    if (nuevo.length === largo) onCompleto?.(nuevo);
  };

  const alTeclado = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key >= "0" && e.key <= "9") {
      e.preventDefault();
      escribir(e.key);
    } else if (e.key === "Backspace") {
      e.preventDefault();
      onChange(value.slice(0, -1));
    }
  };

  return (
    <div
      className="pdv-pinpad"
      role="group"
      aria-label={label}
      aria-describedby={idEstado}
      onKeyDown={alTeclado}
    >
      <div className="pdv-pinpad-puntos" aria-hidden="true">
        {Array.from({ length: largo }, (_, i) => (
          <span key={i} className={`pdv-pinpad-punto ${i < value.length ? "on" : ""}`} />
        ))}
      </div>
      {/* Lo que los puntos dicen en pantalla, dicho para el lector: cuántos
          dígitos van, nunca cuáles. Es región viva porque los puntos son
          `aria-hidden`: sin esto, un toque no produce ninguna señal y no hay
          forma de saber si registró. */}
      <p id={idEstado} className="pdv-sr" aria-live="polite">
        {value.length} de {largo} dígitos
      </p>

      <div className="pdv-pinpad-teclas" data-testid={testid}>
        {TECLAS.map((t) => (
          <button key={t} type="button" onClick={() => escribir(t)}>
            {t}
          </button>
        ))}
        <button
          type="button"
          className="pdv-pinpad-aux"
          aria-label="Borrar todo"
          onClick={() => onChange("")}
        >
          C
        </button>
        <button type="button" onClick={() => escribir("0")}>
          0
        </button>
        <button
          type="button"
          className="pdv-pinpad-aux"
          aria-label="Borrar un dígito"
          onClick={() => onChange(value.slice(0, -1))}
        >
          ⌫
        </button>
      </div>
    </div>
  );
}
