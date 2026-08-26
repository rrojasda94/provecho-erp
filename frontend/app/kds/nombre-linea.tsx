import type { ItemCola } from "@/lib/kds";

/**
 * El plato con todo lo que hay que saber de él: de qué está hecho
 * —los valores de una MitadXMitad, ADR-056— y sus extras y restas colgando
 * debajo (RN-CUP-014).
 *
 * Vive aparte porque lo usan las dos pantallas —estación y despacho— y son
 * tres líneas que no pueden divergir: si una cocina muestra el sabor y la
 * otra no, el plato sale mal en una de las dos.
 */
export default function NombreDeLinea({ item }: { item: ItemCola }) {
  return (
    <span className="kds-nombre">
      {item.producto}
      {/* Primero los valores porque dicen QUÉ es el plato —de qué mitades
          es la pizza—, mientras que extras y restas lo modifican. Mismo
          orden que la comanda impresa: la pantalla y el papel no pueden
          leerse distinto (ADR-056). */}
      {item.valores?.map((valor) => (
        <em key={valor} className="kds-valor">
          &gt; {valor.toUpperCase()}
        </em>
      ))}
      {/* El extra ES el plato: una "Pizza Personal" sin su "+ PEPERONI" es
          una pizza distinta. Va acá dentro y no como ítem suelto. */}
      {item.extras?.map((e) => (
        <em key={e.producto} className="kds-extra">
          + {Number(e.cantidad) === 1 ? "" : `${Number(e.cantidad)}x `}
          {e.producto.toUpperCase()}
        </em>
      ))}
      {/* Las restas van en ámbar y debajo de todo: en una pantalla que se lee
          de reojo, un "sin cebolla" que pasa desapercibido sale como plato
          rehecho (RN-COM-028). */}
      {item.sin?.map((insumo) => (
        <em key={insumo} className="kds-sin">
          SIN {insumo.toUpperCase()}
        </em>
      ))}
    </span>
  );
}
