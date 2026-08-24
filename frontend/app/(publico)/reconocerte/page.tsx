import type { Metadata } from "next";

import { apiFetch } from "@/lib/api";

import ReconocerteCliente from "./reconocerte-cliente";

export const metadata: Metadata = {
  title: "Queremos RE-conocerte | Charlie's Pizzas",
  description:
    "Regístrate y llévate 10 % de descuento en tu siguiente pedido en Charlie's Pizzas.",
};

// La landing se abre desde un QR impreso: cada escaneo tiene que ver el
// estado real de la campaña, no uno cacheado de hace horas. La empresa puede
// terminarla en cualquier momento y esa decisión se aplica al instante.
export const dynamic = "force-dynamic";

type Promocion = {
  nombre: string;
  descuento_porcentaje: string;
  vigente_hasta: string;
  vigencia_cupon_dias: number;
};

/**
 * Pregunta por la promoción antes de dibujar nada.
 *
 * `null` cuando la API dice que no hay (409) o cuando no contesta. Los dos
 * casos se muestran igual —«por ahora no hay promoción»— porque para el
 * cliente son lo mismo, y no tiene sentido explicarle la diferencia entre
 * una campaña terminada y un servicio caído.
 */
async function promocion(): Promise<Promocion | null> {
  try {
    return await apiFetch<Promocion>("/api/v1/sales/publico/reconocerte/promocion");
  } catch {
    return null;
  }
}

export default async function ReconocertePage() {
  const activa = await promocion();

  return (
    <main className="publico-main">
      <header className="reconocerte-hero">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/marcas/charlies.svg"
          alt="Charlie's Pizzas"
          className="reconocerte-marca"
        />
        <h1 className="reconocerte-titulo">
          Queremos <span className="reconocerte-re">RE</span>-conocerte
        </h1>
        {activa ? (
          <p className="reconocerte-bajada">
            Déjanos tus datos y llévate{" "}
            <strong>{Number(activa.descuento_porcentaje)}% de descuento</strong> en tu
            siguiente pedido.
          </p>
        ) : (
          <p className="reconocerte-bajada">
            Por ahora no tenemos una promoción activa. ¡Gracias por pasar!
          </p>
        )}
      </header>

      {activa ? (
        <>
          <ol className="reconocerte-pasos">
            <li>
              <span className="reconocerte-paso-n" aria-hidden>
                1
              </span>
              Completa tus datos
            </li>
            <li>
              <span className="reconocerte-paso-n" aria-hidden>
                2
              </span>
              Recibe tu código al instante
            </li>
            <li>
              <span className="reconocerte-paso-n" aria-hidden>
                3
              </span>
              Muéstralo en caja en tu próxima compra
            </li>
          </ol>
          <ReconocerteCliente
            descuento={Number(activa.descuento_porcentaje)}
            vigenciaDias={activa.vigencia_cupon_dias}
          />
        </>
      ) : null}
    </main>
  );
}
