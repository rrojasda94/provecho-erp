"""Contexto de tenant (ADR-004): aislamiento por filtro de aplicación.

El alcance (empresa + sucursales) se deriva de los claims del JWT, nunca
del body del request. Un cliente ya no puede elegir sobre qué empresa
escribe: como mucho puede *confirmar* la suya.

Excepción explícita — superusuario (permiso `*`) sin empresa asignada:
puede indicar `empresa_id` explícitamente. Es el caso de la cuenta de
administración/setup, que existe antes que cualquier `usuario_sucursal`.
"""

import uuid
from dataclasses import dataclass


class FueraDeAlcance(Exception):
    """El recurso pedido no pertenece al tenant del usuario (→ HTTP 403)."""


@dataclass(frozen=True)
class Tenant:
    usuario_id: uuid.UUID
    empresa_id: uuid.UUID | None
    sucursal_ids: frozenset[uuid.UUID]
    superusuario: bool = False

    def empresa(self, explicito: uuid.UUID | None = None) -> uuid.UUID:
        """`empresa_id` efectivo de la operación."""
        if self.empresa_id is not None:
            if explicito is not None and explicito != self.empresa_id:
                raise FueraDeAlcance("empresa fuera del alcance del usuario")
            return self.empresa_id
        if self.superusuario and explicito is not None:
            return explicito
        raise FueraDeAlcance("usuario sin empresa asignada")

    def filtro_empresa(self, explicito: uuid.UUID | None = None) -> uuid.UUID | None:
        """Variante de `empresa()` para listados: un superusuario sin empresa
        asignada ve todo (None = sin filtro) en vez de recibir 403."""
        if self.empresa_id is None and self.superusuario:
            return explicito
        return self.empresa(explicito)

    def exigir_sucursal(self, sucursal_id: uuid.UUID) -> None:
        if self.superusuario:
            return
        if sucursal_id not in self.sucursal_ids:
            raise FueraDeAlcance("sucursal fuera del alcance del usuario")

    def exigir_empresa(self, empresa_id: uuid.UUID) -> None:
        """Valida un recurso ya cargado (su `empresa_id` viene de la BD)."""
        if self.superusuario and self.empresa_id is None:
            return
        if empresa_id != self.empresa_id:
            raise FueraDeAlcance("recurso fuera del alcance del usuario")

    @classmethod
    def from_claims(cls, claims: dict) -> "Tenant":
        empresa = claims.get("empresa_id")
        return cls(
            usuario_id=uuid.UUID(claims["sub"]),
            empresa_id=uuid.UUID(empresa) if empresa else None,
            sucursal_ids=frozenset(
                uuid.UUID(s) for s in claims.get("sucursales") or []
            ),
            superusuario=bool(claims.get("su")),
        )
