"use client";

import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Cómo sale el papel (ADR-067).
 *
 * El contenido a imprimir se monta en un portal colgado de `<body>` y el CSS
 * de `@media print` esconde todo lo demás. Se descartaron las dos
 * alternativas:
 *
 * - **Un `<iframe>` con su propio documento**: aísla mejor, pero obliga a
 *   duplicar el CSS del ticket como string dentro del iframe, y esa copia se
 *   desincroniza del original a la primera corrección.
 * - **Un PDF armado en el servidor**: hoy el PDF ya existe —lo emite
 *   Factiliza— y bajarlo abre el visor del navegador, que es exactamente el
 *   diálogo que la caja no quiere ver.
 *
 * La impresión sin diálogo **no se resuelve acá**: es una bandera del
 * navegador (`--kiosk-printing`), no código de la aplicación. Con ella,
 * `window.print()` manda directo a la impresora predeterminada; sin ella,
 * sale el diálogo del navegador. Ver `docs/engineering/impresion-termica.md`.
 */
export function HojaImpresion({ children }: { children: React.ReactNode }) {
  const [destino, setDestino] = useState<HTMLElement | null>(null);

  useEffect(() => {
    const nodo = document.createElement("div");
    nodo.className = "impresion-portal";
    document.body.appendChild(nodo);
    setDestino(nodo);
    return () => {
      nodo.remove();
    };
  }, []);

  if (!destino) return null;
  return createPortal(<div className="impresion-hoja">{children}</div>, destino);
}

/**
 * Monta la hoja, espera a que el navegador la haya pintado y recién ahí
 * manda a imprimir.
 *
 * El `requestAnimationFrame` doble no es adorno: `print()` bloquea el hilo,
 * así que llamarlo en el mismo tick en que se monta el contenido saca la
 * hoja **vacía**. Dos cuadros garantizan que el layout ya corrió — incluido
 * el `<img>` del QR, que es un `data:` URI y por eso no espera red.
 */
export function useImpresion() {
  const [listo, setListo] = useState(false);

  useEffect(() => {
    if (!listo) return;
    let vivo = true;
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        if (!vivo) return;
        window.print();
        setListo(false);
      }),
    );
    return () => {
      vivo = false;
    };
  }, [listo]);

  return { imprimiendo: listo, imprimir: useCallback(() => setListo(true), []) };
}
