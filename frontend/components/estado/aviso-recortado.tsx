/**
 * «Esto no es todo lo que hay».
 *
 * Media docena de pantallas del ERP piden una página grande —200 filas— y
 * paginan del lado del navegador. Funciona hasta que la empresa pasa las 200
 * filas, y ahí **una lista incompleta se ve exactamente igual que una
 * completa**: nadie se entera de que le falta el artículo que está buscando,
 * y el modo de falla es que alguien concluya que no existe.
 *
 * Dos pantallas ya avisaban (`compras/facturas`, `inventario/stock`) con el
 * mismo párrafo copiado. Esto es ese párrafo, una sola vez, para poder
 * ponerlo en todas — que era el punto del hallazgo #14 de la auditoría del
 * 2026-08-30.
 *
 * No reemplaza a la paginación de servidor: la reemplaza al silencio. Cuál de
 * las pantallas merece paginación de verdad se decide viendo cuáles avisan
 * seguido, que hasta ahora no se podía saber.
 */
export function AvisoRecortado({
  mostrados,
  total,
  sugerencia,
}: {
  mostrados: number;
  total: number;
  /** Qué hacer para ver el resto, en las palabras de esta pantalla: por qué
   * filtro acotar. Sin esto el aviso informa y no ayuda. */
  sugerencia: string;
}) {
  if (total <= mostrados) return null;
  return (
    <p
      role="status"
      className="rounded-lg bg-status-warning-surface px-3 py-2 text-sm text-status-warning"
    >
      Se muestran <span className="cifra">{mostrados}</span> de{" "}
      <span className="cifra">{total}</span>. {sugerencia}
    </p>
  );
}
