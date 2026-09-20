import { Bloque, Esqueleto, TarjetasEsqueleto } from "@/components/esqueleto";

export default function Cargando() {
  return (
    <Esqueleto>
      <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8">
        <Bloque className="h-9 w-40" />
        <Bloque className="h-10 w-full" />
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 5 }, (_, i) => (
            <Bloque key={i} className="h-7 w-24 rounded-full" />
          ))}
        </div>
        <TarjetasEsqueleto />
      </div>
    </Esqueleto>
  );
}
