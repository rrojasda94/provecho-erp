import Link from "next/link";
import Image from "next/image";

import { apiAuth, apiFetch } from "@/lib/api";
import { obtenerSesion } from "@/lib/auth";

type Contenido = {
  contenido: { hero?: { titulo?: string; subtitulo?: string; cta_texto?: string; cta_url?: string } };
};
type Promocion = { id: string; nombre: string; tipo: string };
type Producto = {
  id: string;
  nombre: string;
  descripcion: string | null;
  precio_desde: string;
  foto_url: string | null;
  disponible: boolean;
};
type Carta = { productos: Producto[] };
type UltimoPedido = {
  numero_orden: number;
  estado: string;
  items: { nombre: string; cantidad: string }[];
} | null;

async function ultimoPedidoDe(token: string): Promise<UltimoPedido> {
  try {
    return await apiAuth<UltimoPedido>("/api/v1/storefront/cuentas/me/ultimo-pedido", { token });
  } catch {
    return null;
  }
}

async function favoritosDe(token: string): Promise<string[]> {
  try {
    return await apiAuth<string[]>("/api/v1/storefront/cuentas/me/favoritos", { token });
  } catch {
    return [];
  }
}

export default async function HomePage() {
  const sesion = await obtenerSesion();
  const [datos, promos, carta, ultimoPedido, favoritosIds] = await Promise.all([
    apiFetch<Contenido>("/api/v1/storefront/publico/contenido"),
    apiFetch<Promocion[]>("/api/v1/storefront/publico/promociones"),
    apiFetch<Carta>("/api/v1/storefront/publico/carta"),
    sesion ? ultimoPedidoDe(sesion.token) : Promise.resolve(null),
    sesion ? favoritosDe(sesion.token) : Promise.resolve([] as string[]),
  ]);

  const hero = datos?.contenido?.hero;
  const promoActiva = promos?.[0];
  const favoritos = (carta?.productos ?? []).filter((p) => favoritosIds.includes(p.id));
  const destacados = favoritos.length > 0 ? favoritos.slice(0, 3) : (carta?.productos ?? []).slice(0, 3);
  const tituloDestacados = favoritos.length > 0 ? "Tus favoritas" : "Las favoritas";

  return (
    <div className="flex flex-col gap-12 pb-16">
      <section className="relative flex min-h-[420px] items-center justify-center bg-negro px-4 text-center text-crema sm:min-h-[520px]">
        <div className="revelar max-w-2xl">
          {promoActiva && (
            <p className="mb-3 inline-block rounded-full bg-rojo px-4 py-1 text-xs font-bold uppercase tracking-wide">
              {promoActiva.nombre}
            </p>
          )}
          <h1 className="font-display text-4xl uppercase leading-tight sm:text-6xl">
            {hero?.titulo ?? "A tu manera"}
          </h1>
          <p className="mt-4 text-base text-crema/90 sm:text-lg">
            {hero?.subtitulo ??
              "Pizza de barrio horneada al momento en Tarapoto desde 2006."}
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              href={hero?.cta_url || "/carta"}
              className="sombra-dura rounded bg-verde px-6 py-3 font-bold uppercase text-negro hover:bg-verde-hover"
            >
              {hero?.cta_texto || "Ver la carta"}
            </Link>
            <Link
              href="/locales"
              className="rounded border-2 border-crema px-6 py-3 font-bold uppercase text-crema hover:bg-crema hover:text-negro"
            >
              Nuestros locales
            </Link>
          </div>
        </div>
      </section>

      {ultimoPedido && (
        <section className="revelar mx-auto w-full max-w-3xl px-4">
          <div className="sombra-dura rounded-lg border-2 border-negro bg-white p-4">
            <p className="text-xs font-bold uppercase text-humo">Tu último pedido</p>
            <p className="font-bold">
              Pedido #{ultimoPedido.numero_orden} — {ultimoPedido.estado}
            </p>
            <p className="text-sm text-humo">
              {ultimoPedido.items.map((it) => `${it.cantidad}x ${it.nombre}`).join(", ")}
            </p>
            <Link href="/cuenta" className="mt-2 inline-block text-sm font-bold text-verde underline">
              Ver mi cuenta
            </Link>
          </div>
        </section>
      )}

      <section className="revelar mx-auto grid max-w-4xl grid-cols-1 gap-6 px-4 text-center sm:grid-cols-3">
        {[
          { n: "1", t: "Elige tu pizza", d: "Arma tu pedido a tu manera desde la carta." },
          { n: "2", t: "Delivery o recojo", d: "Tú decides cómo la quieres recibir." },
          { n: "3", t: "A disfrutar", d: "Recién horneada, con el cariño de siempre." },
        ].map((paso) => (
          <div key={paso.n}>
            <span className="font-display text-3xl text-verde">{paso.n}</span>
            <h3 className="mt-1 font-bold uppercase">{paso.t}</h3>
            <p className="text-sm text-humo">{paso.d}</p>
          </div>
        ))}
      </section>

      {destacados.length > 0 && (
        <section className="mx-auto w-full max-w-5xl px-4">
          <h2 className="revelar font-display text-2xl uppercase text-negro">{tituloDestacados}</h2>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {destacados.map((p) => (
              <Link
                key={p.id}
                href={`/carta/${p.id}`}
                className="revelar sombra-dura flex flex-col overflow-hidden rounded-lg border-2 border-negro bg-white"
              >
                <div className="relative h-40 w-full bg-crema-2">
                  {p.foto_url && (
                    <Image src={p.foto_url} alt={p.nombre} fill className="object-cover" />
                  )}
                </div>
                <div className="flex flex-1 flex-col gap-1 p-3">
                  <h3 className="font-bold">{p.nombre}</h3>
                  <p className="line-clamp-2 flex-1 text-xs text-humo">{p.descripcion}</p>
                  <p className="font-display text-lg text-verde">Desde S/ {p.precio_desde}</p>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="revelar bg-verde py-8 text-center">
        <p className="font-display text-3xl uppercase text-white sm:text-5xl">A tu manera</p>
      </section>
    </div>
  );
}
