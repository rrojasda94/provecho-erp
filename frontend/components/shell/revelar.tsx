"use client";

import { usePathname } from "next/navigation";

/** Entrada de pantalla: 8 px de subida y opacidad, 220 ms.
 *
 * El `key` es el pathname a propósito. El layout no se vuelve a montar al
 * navegar —ese es todo el punto de los layouts anidados— así que una
 * animación CSS aquí se ejecutaría una sola vez en toda la sesión. Cambiar la
 * key remonta el nodo y la animación vuelve a correr en cada navegación, que
 * es lo que suaviza el salto entre pantallas.
 *
 * `children` llega ya renderizado desde el servidor: envolverlo en un
 * componente cliente no arrastra las pantallas al bundle. */
export function Revelar({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div key={pathname} className="revelar h-full">
      {children}
    </div>
  );
}
