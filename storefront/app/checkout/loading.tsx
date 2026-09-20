import { Bloque, Esqueleto } from "@/components/esqueleto";

export default function Cargando() {
  return (
    <Esqueleto>
      <div className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-8">
        <Bloque className="h-8 w-48" />
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="flex flex-col gap-2">
            <Bloque className="h-4 w-40" />
            <Bloque className="h-11 w-full" />
          </div>
        ))}
        <Bloque className="h-12 w-full rounded" />
      </div>
    </Esqueleto>
  );
}
