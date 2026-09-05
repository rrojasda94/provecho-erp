/**
 * El antes y el después de un cambio, con **solo lo que cambió**.
 *
 * `audit_log` guarda los dos diccionarios enteros, y volcarlos crudos es
 * ilegible: en una fila de doce campos, once son iguales y el que importa se
 * pierde entre ellos. Un alta no tiene «antes» y una baja no tiene «después»;
 * los dos casos se dibujan como lo que son.
 */
export function Cambio({
  antes,
  despues,
}: {
  antes: Record<string, unknown> | null;
  despues: Record<string, unknown> | null;
}) {
  const claves = [...new Set([...Object.keys(antes ?? {}), ...Object.keys(despues ?? {})])]
    .filter((k) => texto(antes?.[k]) !== texto(despues?.[k]))
    .sort();

  if (claves.length === 0) {
    return <span className="text-xs text-gray">—</span>;
  }

  return (
    <ul className="flex flex-col gap-0.5">
      {claves.map((k) => (
        <li key={k} className="text-xs">
          <span className="font-semibold text-dark">{k}</span>{" "}
          {antes && k in antes && (
            <span className="cifra text-gray line-through">{texto(antes[k])}</span>
          )}{" "}
          {despues && k in despues && (
            <span className="cifra text-foreground">{texto(despues[k])}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Un valor del JSONB como se lee: los objetos anidados se serializan y se
 * recortan, porque una fila de tabla no es el lugar para desplegar un árbol —
 * si hace falta el detalle completo, la consulta a la base lo tiene. */
function texto(valor: unknown): string {
  if (valor === null || valor === undefined) return "—";
  if (typeof valor === "object") {
    const serializado = JSON.stringify(valor);
    return serializado.length > 80 ? `${serializado.slice(0, 80)}…` : serializado;
  }
  return String(valor);
}
