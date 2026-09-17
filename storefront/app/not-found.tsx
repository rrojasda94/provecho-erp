import Link from "next/link";

export default function NoEncontrado() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-24 text-center">
      <p className="font-display text-6xl text-verde">404</p>
      <p className="text-humo">No encontramos esa página.</p>
      <Link
        href="/"
        className="sombra-dura rounded bg-verde px-6 py-3 font-bold uppercase text-negro hover:bg-verde-hover"
      >
        Volver al inicio
      </Link>
    </div>
  );
}
