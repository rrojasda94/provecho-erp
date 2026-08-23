"""Ítem de receta: un artículo (insumo/subreceta) con cantidad y merma.

**La unidad.** `unidad_medida_id` es NULL casi siempre, y NULL significa "la
del artículo" — el comportamiento que rigió desde ADR-023 y que sigue siendo
el correcto por defecto: la receta hereda la unidad del insumo que usa.

Lo que ADR-023 descartó era otra cosa: una unidad *libre*, que permitiera
decir "0.5" sin que nadie supiera de qué. Eso sí serían dos verdades. Una
unidad **de la misma categoría** que la del artículo no lo es: RN-UDM-001 la
admite desde siempre y `unidad_medida.ratio` la convierte sin ambigüedad. La
diferencia importa porque es cómo se compra y cómo se cocina — el aceite
entra por litros y la receta lleva 30 ml, y obligar a escribir "0.03" es
exactamente el error de tipeo que después aparece como faltante.

Al descontar stock, la cantidad se convierte a la unidad del artículo
(`domain.rules.convertir_cantidad`), que sigue siendo la que manda.

**La condición.** `aplica_valores` es lo que hace que una receta valga para
muchas combinaciones en vez de una. Es el `bom_product_template_attribute_value_ids`
de Odoo ("Apply on Variants"): la línea solo cuenta si la combinación
elegida coincide con **al menos un valor por cada atributo** nombrado en la
condición (`domain.rules.aplica_a_variante`, ADR-056). NULL o `[]` = siempre.

Sin esto, una pizza mitad-y-mitad de 19 sabores son 361 recetas. Con esto es
una receta de 26 líneas — que es exactamente el archivo que Charlie's ya
tiene en Odoo.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import JsonB, TimestampMixin, UuidPkMixin


class RecetaItem(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "receta_item"

    receta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("receta.id"))
    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("articulo.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    # NULL = la del artículo. Si viene, tiene que ser de la misma categoría
    # de UdM que la del artículo (RN-UDM-001, RN-UDM-005).
    unidad_medida_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("unidad_medida.id"), nullable=True
    )
    merma_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal(0))
    # Lo que el usuario tecleó si la cantidad salió de una operación
    # ("1000/3"). Se guarda para poder reeditarla, no para recalcularla: la
    # verdad es `cantidad`, ya redondeada a los decimales de la UdM.
    expresion: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Array de `producto_atributo_valor.id` como texto. NULL/[] = la línea
    # aplica a toda combinación (ADR-056).
    aplica_valores: Mapped[list | None] = mapped_column(JsonB, nullable=True)
    # Para que exportar dos veces dé el mismo archivo. Sin orden explícito
    # las líneas salen como las devuelva la base, y un diff contra el
    # archivo anterior deja de servir para ver qué cambió de verdad.
    orden: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
