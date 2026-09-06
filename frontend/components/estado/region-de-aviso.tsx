/**
 * El aviso pasajero del KDS y del PDV, anunciado también por voz.
 *
 * Las dos pantallas avisan con una píldora flotante que aparece y se va sola:
 * «pedido listo», «no se pudo guardar», «faltó un dígito». Quien no la ve no
 * se entera de nada — y son justo las dos pantallas que se usan de pie,
 * mirando otra cosa (hallazgo #17 de la auditoría del 2026-08-30).
 *
 * **La región vive siempre**, y lo que aparece y desaparece es el mensaje de
 * adentro. Es la parte que se hace mal seguido: un `{aviso && <div
 * role="status">…</div>}` monta el `role` **junto con** el texto, y un lector
 * de pantalla anuncia los cambios de una región viva — no su aparición. Con
 * el contenedor montado desde el principio, cada mensaje nuevo es un cambio y
 * se lee.
 *
 * `role="status"` y no `alert`: son avisos de lo que pasó, no interrupciones.
 * `alert` corta lo que el lector esté leyendo, y en una cocina con cinco
 * pedidos en pantalla eso es peor que el silencio. El `aria-live` va
 * explícito aunque `status` ya lo implique: se lee al revisar el código, que
 * es donde hay que poder verlo.
 */
export function RegionDeAviso({
  texto,
  clase,
}: {
  /** Vacío —o `null`— mientras no hay nada que decir. */
  texto: string | null;
  /** La píldora de cada pantalla: `kds-aviso` o `pdv-aviso`. Va en el hijo y
   * no en la región para que el contenedor siempre montado no dibuje una
   * cápsula vacía flotando. */
  clase: string;
}) {
  return (
    <div role="status" aria-live="polite">
      {texto && <div className={clase}>{texto}</div>}
    </div>
  );
}
