"""DecisionGerencial: acta de la decisión que tomó Gerencia (RN-GER-002).

Entidad transversal (vive en `shared`, mismo criterio que `Comprobante` y
`ParametroEmpresa`): Gerencia es autoridad y documentos, no un módulo con
lógica propia — la facultad de aprobar es un permiso de rol, no una tabla.
Lo que sí necesita existir como dato es el **acta**: una decisión verbal no
tiene validez operativa.

Referencia polimórfica (`referencia_tipo` + `referencia_id`) a propósito: la
decisión aplica a una OC escalada, a un requerimiento de activo, a una
campaña sobre presupuesto o a una sanción, y ninguno de esos módulos debe
ganar una FK hacia `shared` ni `shared` una FK hacia ellos — sería el
acoplamiento que la arquitectura modular evita. El módulo consumidor
resuelve `referencia_id` contra su propia tabla cuando lo necesita.

**No** reemplaza el rastro de `parametro_empresa` (propuesta/aprobación con
`motivo`, RN-GER-009): ese par ya registra quién, qué, cuándo y con qué
sustento — por eso se descartó `parametro_empresa.decision_gerencial_id`.
Esta tabla es para las decisiones que **no** tienen su propio flujo tipado.
"""

import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.model_base import SoftDeleteMixin, TimestampMixin, UuidPkMixin

TIPOS = ("aprobacion", "directiva", "accion_correctiva", "decision_estrategica")
RESULTADOS = (
    "aprobado",
    "aprobado_con_condiciones",
    "rechazado",
    "diferido",
    "elevado_a_socios",
)


class DecisionGerencial(Base, UuidPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "decision_gerencial"
    __table_args__ = (
        # El acceso real es "qué se decidió sobre esto", desde el módulo que
        # tiene la OC/campaña/sanción en pantalla.
        Index(
            "ix_decision_gerencial_referencia",
            "referencia_tipo",
            "referencia_id",
        ),
    )

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    tipo: Mapped[str] = mapped_column(
        Enum(*TIPOS, name="tipo_decision_gerencial", native_enum=False)
    )
    # Polimórfico, sin FK — ver docstring. `referencia_tipo` es el nombre de
    # la tabla referida ("orden_compra", "campana", "trabajador"...).
    referencia_tipo: Mapped[str] = mapped_column(String(50))
    referencia_id: Mapped[uuid.UUID]

    # Quién decidió: el `usuario` que ejerció el permiso, no un trabajador
    # suelto — es la misma identidad que autenticó y que audita el sistema.
    decidido_por_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"))
    sustento: Mapped[str] = mapped_column(Text)
    resultado: Mapped[str] = mapped_column(
        Enum(*RESULTADOS, name="resultado_decision_gerencial", native_enum=False)
    )
    # Obligatorias de hecho si `resultado=aprobado_con_condiciones`; la regla
    # vive en la capa de aplicación, no en el esquema (el resto de resultados
    # las deja vacías legítimamente).
    condiciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Qué área ejecuta lo decidido (RN-GER-005: Gerencia decide, el área
    # competente ejecuta con el debido proceso). Catálogo en
    # `src.shared.parametros.MODULOS`.
    ejecuta_area: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fecha: Mapped[date] = mapped_column(Date)
    # Acta escaneada/firmada, si la hay. La decisión vale igual sin archivo:
    # exigirlo bloquearía registrar la decisión el día que se tomó.
    archivo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("archivo.id"), nullable=True
    )
