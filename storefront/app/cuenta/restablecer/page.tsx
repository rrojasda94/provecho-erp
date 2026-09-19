import Link from "next/link";
import type { Metadata } from "next";

import { RestablecerForm } from "./restablecer-form";

export const metadata: Metadata = { title: "Elegir una clave nueva" };

export default async function RestablecerPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;
  return (
    <div className="mx-auto flex max-w-sm flex-col gap-4 px-4 py-16">
      <h1 className="font-display text-2xl uppercase text-negro">Elige una clave nueva</h1>
      {token ? (
        <RestablecerForm token={token} />
      ) : (
        <p className="text-sm text-humo">
          Este enlace no está completo.{" "}
          <Link href="/cuenta/recuperar" className="font-bold text-verde underline">
            Pide uno nuevo
          </Link>
          .
        </p>
      )}
    </div>
  );
}
