"""DTOs (pydantic) del módulo marketing."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoCampana = Literal["notoriedad", "impulso_venta", "lanzamiento", "medios", "evento"]
TipoLead = Literal["contacto", "visita", "cupon", "registro"]
CanalEncuesta = Literal["pos", "whatsapp", "link"]


class CampanaCreate(BaseModel):
    marca_id: uuid.UUID
    nombre: str = Field(min_length=3, max_length=120)
    tipo: TipoCampana
    canal: str = Field(min_length=2, max_length=50)
    objetivo: str | None = Field(default=None, max_length=255)
    publico_objetivo: str | None = Field(default=None, max_length=255)
    presupuesto: Decimal | None = Field(default=None, ge=0)
    kpi: str | None = Field(default=None, max_length=255)
    idempotency_key: str = Field(min_length=8, max_length=100)
    # Solo lo usa un superusuario sin empresa asignada (ADR-004).
    empresa_id: uuid.UUID | None = None


class BriefUpdate(BaseModel):
    objetivo: str | None = Field(default=None, max_length=255)
    publico_objetivo: str | None = Field(default=None, max_length=255)
    presupuesto: Decimal | None = Field(default=None, ge=0)
    kpi: str | None = Field(default=None, max_length=255)


class CampanaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    empresa_id: uuid.UUID
    marca_id: uuid.UUID
    nombre: str
    tipo: str
    canal: str
    objetivo: str | None
    publico_objetivo: str | None
    presupuesto: Decimal | None
    kpi: str | None
    estado: str
    aprobada_por: uuid.UUID | None


class ImplementacionCreate(BaseModel):
    sucursal_id: uuid.UUID
    completa: bool
    incidencia: str | None = Field(default=None, max_length=255)
    fecha: date | None = None


class ImplementacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campana_id: uuid.UUID
    sucursal_id: uuid.UUID
    fecha: date
    completa: bool
    incidencia: str | None


class PiezaCreate(BaseModel):
    marca_id: uuid.UUID
    titulo: str = Field(min_length=3, max_length=150)
    canal: str = Field(min_length=2, max_length=50)
    fecha_publicacion: date
    campana_id: uuid.UUID | None = None
    pertinente_marca: bool = False
    uso_marca_validado: bool = False


class PiezaValidar(BaseModel):
    pertinente_marca: bool | None = None
    uso_marca_validado: bool | None = None


class PiezaPublicar(BaseModel):
    metricas: dict | None = None


class PiezaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campana_id: uuid.UUID | None
    marca_id: uuid.UUID
    titulo: str
    canal: str
    fecha_publicacion: date
    pertinente_marca: bool
    uso_marca_validado: bool
    estado: str
    metricas: dict | None


class LeadCreate(BaseModel):
    campana_id: uuid.UUID
    canal: str = Field(min_length=2, max_length=50)
    tipo: TipoLead
    contacto: str | None = Field(default=None, max_length=120)
    cliente_id: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=100)


class LeadAtribuir(BaseModel):
    venta_id: uuid.UUID


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campana_id: uuid.UUID
    canal: str
    tipo: str
    contacto: str | None
    cliente_id: uuid.UUID | None
    venta_id: uuid.UUID | None


class EncuestaCreate(BaseModel):
    venta_id: uuid.UUID
    canal: CanalEncuesta


class EncuestaRespuesta(BaseModel):
    puntaje: int = Field(ge=1, le=5)
    comentario: str | None = Field(default=None, max_length=500)


class EncuestaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    venta_id: uuid.UUID
    cliente_id: uuid.UUID
    canal: str
    fecha_envio: datetime
    fecha_respuesta: datetime | None
    puntaje: int | None
    comentario: str | None
    estado: str
