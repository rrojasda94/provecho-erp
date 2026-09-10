import type { Metadata } from "next";

import { consultarSeguimiento } from "./actions";
import SeguimientoCliente from "./seguimiento-cliente";

export const metadata: Metadata = {
  title: "Seguimiento de tu pedido | Grupo Majambo",
  description: "Sigue en vivo por dónde va tu pedido.",
};

// El repartidor se mueve y la entrega cambia de estado en cualquier momento
// del día: la primera carga tiene que ver el estado real, no uno cacheado
// desde el build. `SeguimientoCliente` sondea el resto, después de esta.
export const dynamic = "force-dynamic";

export default async function SeguimientoPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const inicial = await consultarSeguimiento(token).catch(() => null);

  if (!inicial) {
    return (
      <main className="publico-main">
        <header className="postular-hero">
          <p className="postular-sobretitulo">Seguimiento de pedido</p>
          <h1 className="postular-titulo">Este enlace ya no está disponible</h1>
          <p className="postular-bajada">
            Puede que el pedido ya se haya cerrado hace un tiempo o que el enlace esté
            vencido. Si necesitas ayuda, escríbenos a la sucursal donde compraste.
          </p>
        </header>
      </main>
    );
  }

  return (
    <main className="publico-main">
      <header className="postular-hero">
        <p className="postular-sobretitulo">{inicial.sucursal.nombre}</p>
        <h1 className="postular-titulo">
          {inicial.numero_orden ? `Pedido #${inicial.numero_orden}` : "Tu pedido"}
        </h1>
      </header>

      <SeguimientoCliente token={token} inicial={inicial} />
    </main>
  );
}
