import { Bloque, Esqueleto } from "@/components/esqueleto";

export default function Cargando() {
  return (
    <Esqueleto>
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
        <Bloque className="h-8 w-2/3" />
        <Bloque className="h-56 w-full" />
        <Bloque className="h-4 w-24" />
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 3 }, (_, i) => (
            <Bloque key={i} className="h-12 w-36 rounded" />
          ))}
        </div>
        <Bloque className="h-12 w-full rounded" />
      </div>
    </Esqueleto>
  );
}
