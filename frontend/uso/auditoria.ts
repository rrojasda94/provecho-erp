import type { Page } from "@playwright/test";

/**
 * Auditoría geométrica de una pantalla: qué controles existen en el DOM pero
 * **no se pueden tocar** en este ancho, y si el diálogo abierto —cuando lo
 * hay— quedó centrado.
 *
 * Responde la pregunta que una captura no responde sola —¿este botón está
 * dibujado fuera de un contenedor que lo recorta?— en las tres medidas y sin
 * criterio humano.
 */
export type Hallazgo = {
  clase: "desborde-pagina" | "control-recortado" | "dialogo-descentrado";
  detalle: string;
};

export async function auditar(page: Page): Promise<Hallazgo[]> {
  return page.evaluate(() => {
    const nombre = (el: Element) => {
      const t = (el.getAttribute("aria-label") ?? el.textContent ?? "").trim();
      const cls = el.className.toString().split(" ")[0] || "-";
      return `${el.tagName.toLowerCase()}.${cls} «${t.slice(0, 36)}»`;
    };

    /** Ancestros que recortan, de adentro hacia afuera.
     *
     * La cadena se corta en un `<dialog>` modal: un modal se pinta en el
     * *top layer*, fuera del flujo de sus ancestros del DOM — seguir subiendo
     * reporta como recortado todo formulario que viva dentro de una tabla con
     * scroll horizontal, que es casi todos. */
    const recortadores = (el: Element) => {
      const lista: Element[] = [];
      let p: Element | null = el.parentElement;
      while (p) {
        const s = getComputedStyle(p);
        if (/hidden|clip|auto|scroll/.test(s.overflowX + s.overflowY)) lista.push(p);
        if (p.matches("dialog:modal")) break;
        p = p.parentElement;
      }
      return lista;
    };

    /** Ejes en los que `r` cae fuera de la caja visible `cr`. */
    const fuera = (r: DOMRect, cr: DOMRect) => ({
      x: r.left > cr.right - 1 || r.right < cr.left + 1,
      y: r.top > cr.bottom - 1 || r.bottom < cr.top + 1,
    });

    /** Ejes en los que `c` tiene scroll de verdad, o sea contenido al que se
     * llega scrolleando. */
    const scrollea = (c: Element) => {
      const s = getComputedStyle(c);
      return {
        x: /auto|scroll/.test(s.overflowX) && c.scrollWidth > c.clientWidth + 1,
        y: /auto|scroll/.test(s.overflowY) && c.scrollHeight > c.clientHeight + 1,
      };
    };

    /** El primer contenedor que deja a `el` fuera de su caja visible sin
     * scroll que lo alcance, o `null` si se llega a él.
     *
     * La búsqueda termina en el primer contenedor que lo deja afuera, llegue
     * o no: de ahí para arriba los contenedores ya no hablan de este control
     * sino del contenedor entero. */
    const recortadoPor = (el: Element): Element | null => {
      const r = el.getBoundingClientRect();
      for (const c of recortadores(el)) {
        const f = fuera(r, c.getBoundingClientRect());
        if (!f.x && !f.y) continue;
        const s = scrollea(c);
        return (f.x && s.x) || (f.y && s.y) ? null : c;
      }
      return null;
    };

    /** ¿Vale la pena medir este elemento? Un control de tamaño cero o
     * escondido no es una opción inalcanzable, es una que no está.
     * `checkVisibility` cubre de una vez el `display: none` propio, el de
     * cualquier ancestro y el `<dialog>` cerrado — sin eso, los diálogos
     * montados y cerrados de cada pantalla se reportan como rotos. */
    const cuenta = (el: Element) => {
      if (!(el as HTMLElement).checkVisibility()) return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    };

    /** Fuera del árbol de accesibilidad no es una opción que se esté
     * escondiendo: es plomería. Base UI (`Select`, `Combobox`) monta un
     * `<input>` así por debajo de cada uno —1×1 px, `aria-hidden="true"`—
     * para que el valor viaje en un `<form>` nativo; el control de verdad es
     * el disparador visible, que se audita aparte. Sin este filtro, todo
     * `Select` del ERP reportaba un input "recortado" que nadie usa ni puede
     * tocar.
     *
     * No se filtra por `tabindex="-1"` a secas: un menú o un radiogroup con
     * *roving tabindex* deja así a todo ítem salvo el activo, y siguen
     * siendo clickeables de verdad — excluirlos taparía un recorte real. */
    const esPlomeria = (el: Element) => el.getAttribute("aria-hidden") === "true";

    const controlesRecortados = () =>
      [...document.querySelectorAll("button, a[href], input, select, textarea, [role=button]")]
        .filter((el) => !esPlomeria(el))
        .filter(cuenta)
        .map((el) => ({ el, jaula: recortadoPor(el) }))
        .filter((x) => x.jaula)
        .map((x) => ({
          clase: "control-recortado",
          detalle: `${nombre(x.el)} fuera de ${nombre(x.jaula!)}`,
        }));

    /** Un panel a pantalla completa (el bloqueo del PDV) no se juzga por su
     * centro: ya ocupa todo. */
    const desvio = (r: DOMRect) =>
      r.width >= innerWidth - 2 && r.height >= innerHeight - 2
        ? { x: 0, y: 0 }
        : {
            x: Math.abs(r.left + r.width / 2 - innerWidth / 2),
            y: Math.abs(r.top + r.height / 2 - innerHeight / 2),
          };

    const dialogosDescentrados = () =>
      [...document.querySelectorAll("dialog[open], [role=dialog]")]
        .filter(cuenta)
        .map((d) => ({ d, v: desvio(d.getBoundingClientRect()) }))
        .filter((x) => x.v.x > 2 || x.v.y > 2)
        .map((x) => ({
          clase: "dialogo-descentrado",
          detalle: `${nombre(x.d)} desvío x=${Math.round(x.v.x)} y=${Math.round(x.v.y)}`,
        }));

    const raiz = document.scrollingElement ?? document.documentElement;
    const desbordePagina =
      raiz.scrollWidth > raiz.clientWidth + 1
        ? [
            {
              clase: "desborde-pagina",
              detalle: `scrollWidth ${raiz.scrollWidth} > clientWidth ${raiz.clientWidth}`,
            },
          ]
        : [];

    return [
      ...desbordePagina,
      ...controlesRecortados(),
      ...dialogosDescentrados(),
    ] as never;
  });
}
