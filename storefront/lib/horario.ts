/** Formato del horario de atención (`sucursal.horario_atencion`, ver
 * `docs/architecture/data-model.md` §18). Espeja
 * `src/modules/storefront/domain/rules.py::abierto_ahora` en la forma que
 * lee, no en el cálculo — el "abierto ahora" ya lo calcula el backend
 * (`SucursalPublicaOut.abierto_ahora`) para no depender del reloj del
 * navegador de cada visitante. */

export type Horario = Record<string, [string, string][]> | null;

const DIAS: { clave: string; etiqueta: string }[] = [
  { clave: "lun", etiqueta: "Lunes" },
  { clave: "mar", etiqueta: "Martes" },
  { clave: "mie", etiqueta: "Miércoles" },
  { clave: "jue", etiqueta: "Jueves" },
  { clave: "vie", etiqueta: "Viernes" },
  { clave: "sab", etiqueta: "Sábado" },
  { clave: "dom", etiqueta: "Domingo" },
];

export function filasDeHorario(horario: Horario): { etiqueta: string; texto: string }[] {
  if (!horario) return DIAS.map((d) => ({ etiqueta: d.etiqueta, texto: "Consultar" }));
  return DIAS.map((d) => {
    const tramos = horario[d.clave];
    if (!Array.isArray(tramos)) return { etiqueta: d.etiqueta, texto: "Consultar" };
    if (tramos.length === 0) return { etiqueta: d.etiqueta, texto: "Cerrado" };
    return {
      etiqueta: d.etiqueta,
      texto: tramos.map(([desde, hasta]) => `${desde} – ${hasta}`).join(", "),
    };
  });
}
