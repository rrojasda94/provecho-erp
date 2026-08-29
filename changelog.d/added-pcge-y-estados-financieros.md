- **El plan de cuentas de fábrica es el PCGE** (2026-08-29, ADR-081). El
  módulo de contabilidad nacía con el plan vacío, así que cada empresa
  inventaba sus códigos y terminaba con un plan distinto al del contador
  externo. El Plan Contable General Empresarial 2019 —obligatorio en el
  Perú— ahora viene cargado y se siembra con un botón en Contabilidad → Plan
  de cuentas. Vive en código y no en configuración porque no es una decisión
  de la empresa: es la misma norma para las tres empresas del grupo.
- **Los asientos automáticos son los asientos peruanos completos** (ADR-081).
  `regla_asiento` mapeaba una cuenta de debe y una de haber por evento, y con
  dos líneas no se puede escribir ningún asiento real: una venta gravada son
  tres (cobrar, IGV, ingreso) y una compra cinco, contando el asiento de
  destino que ingresa la mercadería al almacén. El IGV, que es la mitad de la
  obligación tributaria del mes, no aparecía en ninguna parte. Ahora cada
  evento tiene su plantilla con códigos del PCGE y `regla_asiento` pasa a ser
  el override de quien quiera otra cosa. La tasa de IGV sale de la empresa
  (cero en Amazonía) y se desagrega por diferencia contra el total, para que
  base + IGV sea exactamente lo que se cobró.
- **Estados financieros** (ADR-081): balance de comprobación, libro mayor,
  Estado de Situación Financiera y Estado de Resultados, en Contabilidad →
  Estados financieros. La pregunta «¿cómo está mi empresa?» antes obligaba a
  exportar los asientos y sumarlos afuera. Se calculan agregando el mayor en
  cada consulta, sin tabla de saldos: un saldo materializado es un segundo
  lugar donde vive la verdad. El Estado de Resultados se presenta **por
  naturaleza** —el de por función necesita los asientos de destino del
  elemento 9 contra la 79, que todavía se hacen a mano— y trae su resultado
  contrastado contra el del libro completo, de modo que un descuadre se ve en
  la pantalla en vez de haber que buscarlo.
- **Un asiento ya no se imputa contra un rubro que agrupa a otras cuentas**
  (ADR-081). Cargar contra «42 Cuentas por pagar comerciales» dejaba el mayor
  sin decir contra qué divisionaria y el rubro con movimiento propio además
  del de sus hijas: el balance seguía cuadrando y el detalle desaparecía.
