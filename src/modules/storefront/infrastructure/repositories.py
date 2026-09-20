"""Repositorios de `storefront`."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.storefront.infrastructure.models import (
    StorefrontContenido,
    StorefrontCuenta,
    StorefrontDireccion,
    StorefrontFavorito,
    StorefrontPedido,
    StorefrontPedidoItem,
    StorefrontRefreshToken,
)


class ContenidoRepo:
    def __init__(self, session: Session):
        self.session = session

    def get(self, marca_id: uuid.UUID, clave: str) -> StorefrontContenido | None:
        return self.session.scalar(
            select(StorefrontContenido).where(
                StorefrontContenido.marca_id == marca_id,
                StorefrontContenido.clave == clave,
            )
        )

    def listar(self, marca_id: uuid.UUID) -> list[StorefrontContenido]:
        return list(
            self.session.scalars(
                select(StorefrontContenido).where(
                    StorefrontContenido.marca_id == marca_id
                )
            )
        )

    def add(self, contenido: StorefrontContenido) -> StorefrontContenido:
        self.session.add(contenido)
        self.session.flush()
        return contenido


class CuentaRepo:
    def __init__(self, session: Session):
        self.s = session

    def get(self, cuenta_id: uuid.UUID) -> StorefrontCuenta | None:
        cuenta = self.s.get(StorefrontCuenta, cuenta_id)
        return cuenta if cuenta and cuenta.deleted_at is None else None

    def get_by_email(self, email: str) -> StorefrontCuenta | None:
        return self.s.scalar(
            select(StorefrontCuenta).where(
                StorefrontCuenta.email == email.strip().lower(),
                StorefrontCuenta.deleted_at.is_(None),
            )
        )

    def get_by_google_sub(self, google_sub: str) -> StorefrontCuenta | None:
        return self.s.scalar(
            select(StorefrontCuenta).where(
                StorefrontCuenta.google_sub == google_sub,
                StorefrontCuenta.deleted_at.is_(None),
            )
        )

    def get_by_documento(self, numero_documento: str) -> StorefrontCuenta | None:
        return self.s.scalar(
            select(StorefrontCuenta).where(
                StorefrontCuenta.numero_documento == numero_documento.strip(),
                StorefrontCuenta.deleted_at.is_(None),
            )
        )

    def get_by_telefono(self, telefono: str) -> StorefrontCuenta | None:
        return self.s.scalar(
            select(StorefrontCuenta).where(
                StorefrontCuenta.telefono == telefono.strip(),
                StorefrontCuenta.deleted_at.is_(None),
            )
        )

    def add(self, cuenta: StorefrontCuenta) -> StorefrontCuenta:
        self.s.add(cuenta)
        self.s.flush()
        return cuenta


class RefreshTokenRepo:
    def __init__(self, session: Session):
        self.s = session

    def get_by_hash(self, token_hash: str) -> StorefrontRefreshToken | None:
        return self.s.scalar(
            select(StorefrontRefreshToken).where(
                StorefrontRefreshToken.token_hash == token_hash
            )
        )

    def add(self, token: StorefrontRefreshToken) -> StorefrontRefreshToken:
        self.s.add(token)
        self.s.flush()
        return token

    def revocar_sesion(self, sesion_id: uuid.UUID) -> None:
        for tok in self.s.scalars(
            select(StorefrontRefreshToken).where(
                StorefrontRefreshToken.sesion_id == sesion_id
            )
        ):
            tok.revocado = True

    def revocar_cuenta(self, cuenta_id: uuid.UUID) -> None:
        """Cierra todas las sesiones de la cuenta (cambio de clave)."""
        for tok in self.s.scalars(
            select(StorefrontRefreshToken).where(
                StorefrontRefreshToken.cuenta_id == cuenta_id,
                StorefrontRefreshToken.revocado.is_(False),
            )
        ):
            tok.revocado = True


class DireccionRepo:
    def __init__(self, session: Session):
        self.s = session

    def get(self, direccion_id: uuid.UUID) -> StorefrontDireccion | None:
        d = self.s.get(StorefrontDireccion, direccion_id)
        return d if d and d.deleted_at is None else None

    def listar(self, cuenta_id: uuid.UUID) -> list[StorefrontDireccion]:
        return list(
            self.s.scalars(
                select(StorefrontDireccion).where(
                    StorefrontDireccion.cuenta_id == cuenta_id,
                    StorefrontDireccion.deleted_at.is_(None),
                )
            )
        )

    def add(self, direccion: StorefrontDireccion) -> StorefrontDireccion:
        self.s.add(direccion)
        self.s.flush()
        return direccion


class FavoritoRepo:
    def __init__(self, session: Session):
        self.s = session

    def get(
        self, cuenta_id: uuid.UUID, producto_comercial_id: uuid.UUID
    ) -> StorefrontFavorito | None:
        return self.s.scalar(
            select(StorefrontFavorito).where(
                StorefrontFavorito.cuenta_id == cuenta_id,
                StorefrontFavorito.producto_comercial_id == producto_comercial_id,
            )
        )

    def listar(self, cuenta_id: uuid.UUID) -> list[StorefrontFavorito]:
        return list(
            self.s.scalars(
                select(StorefrontFavorito).where(
                    StorefrontFavorito.cuenta_id == cuenta_id
                )
            )
        )

    def add(self, favorito: StorefrontFavorito) -> StorefrontFavorito:
        self.s.add(favorito)
        self.s.flush()
        return favorito

    def borrar(self, favorito: StorefrontFavorito) -> None:
        self.s.delete(favorito)


class PedidoRepo:
    def __init__(self, session: Session):
        self.s = session

    def get(self, pedido_id: uuid.UUID) -> StorefrontPedido | None:
        return self.s.get(StorefrontPedido, pedido_id)

    def get_by_idempotency(self, key: str) -> StorefrontPedido | None:
        return self.s.scalar(
            select(StorefrontPedido).where(StorefrontPedido.idempotency_key == key)
        )

    def get_by_pago_externo(self, id_externo: str) -> StorefrontPedido | None:
        return self.s.scalar(
            select(StorefrontPedido).where(StorefrontPedido.pago_id_externo == id_externo)
        )

    def get_by_venta(self, venta_id: uuid.UUID) -> StorefrontPedido | None:
        return self.s.scalar(
            select(StorefrontPedido).where(StorefrontPedido.venta_id == venta_id)
        )

    def listar_de_cuenta(self, cuenta_id: uuid.UUID) -> list[StorefrontPedido]:
        return list(
            self.s.scalars(
                select(StorefrontPedido)
                .where(StorefrontPedido.cuenta_id == cuenta_id)
                .order_by(StorefrontPedido.created_at.desc())
            )
        )

    def add(self, pedido: StorefrontPedido) -> StorefrontPedido:
        self.s.add(pedido)
        self.s.flush()
        return pedido


class PedidoItemRepo:
    def __init__(self, session: Session):
        self.s = session

    def listar(self, pedido_id: uuid.UUID) -> list[StorefrontPedidoItem]:
        return list(
            self.s.scalars(
                select(StorefrontPedidoItem).where(
                    StorefrontPedidoItem.pedido_id == pedido_id
                )
            )
        )

    def add(self, item: StorefrontPedidoItem) -> StorefrontPedidoItem:
        self.s.add(item)
        self.s.flush()
        return item
