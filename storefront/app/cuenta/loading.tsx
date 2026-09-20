import { Bloque, Esqueleto } from "@/components/esqueleto";

export default function Cargando() {
  return (
    <Esqueleto>
      <div className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-8">
        <Bloque className="h-8 w-40" />
        <Bloque className="h-24 w-full" />
        <Bloque className="h-5 w-32" />
        <Bloque className="h-32 w-full" />
      </div>
    </Esqueleto>
  );
}
