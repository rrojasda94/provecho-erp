"""CHECK constraint por cada Enum sin tipo nativo

`Enum(..., native_enum=False)` no emite ningún CHECK por sí solo
(`create_constraint` vale `False` desde SQLAlchemy 1.4): un valor fuera del
vocabulario entra sin ruido —la columna es un VARCHAR pelado— y revienta con
`LookupError` → 500 en cada lectura posterior de esa fila. No es un alta
rechazada, es una fila envenenada para todos hasta que alguien la corrija a
mano en la base (ver `docs/roadmap/deuda/transversal.md`, "112 columnas
Enum(native_enum=False) sin CHECK", y la migración `c9f4a2e70b18` que cerró
el primer caso, `persona.tipo_documento`, con el mismo patrón que esta).

114 columnas en 65 tablas. Antes de cada CHECK, un UPDATE saca a NULL
cualquier valor guardado fuera del vocabulario —solo en las columnas
nullable—; las NOT NULL no tienen a dónde sanear un valor inválido sin
inventar un dato, así que el CREATE CONSTRAINT falla ruidoso si hay una fila
sucia, que es preferible a adivinar.

Sin CHECK explícito (no `create_constraint=True`): ese queda ligado al tipo
(`_type_bound`) y `alembic check` lo ve como un constraint sobrante en cada
corrida contra el modelo, que ya declara el CHECK aparte en
`__table_args__`.

Revision ID: c4f3e14f5bce
Revises: c7a1e94b2d38
Create Date: 2026-09-06 20:15:17.110879

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4f3e14f5bce"
down_revision: str | None = "c7a1e94b2d38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "tipo_acta",
        "acta",
        sa.text("tipo IN ('reunion', 'incidente', 'entrega_cargo', 'arqueo', 'verificacion')"),
    )
    op.create_check_constraint(
        "estado_ajuste", "ajuste", sa.text("estado IN ('pendiente', 'aprobado', 'rechazado')")
    )
    op.create_check_constraint(
        "motivo_ajuste",
        "ajuste",
        sa.text("motivo IN ('sobrante', 'faltante', 'merma', 'error_registro')"),
    )
    op.create_check_constraint(
        "tipo_amonestacion", "amonestacion", sa.text("tipo IN ('verbal', 'escrita')")
    )
    op.create_check_constraint(
        "origen_archivo", "archivo", sa.text("origen IN ('generado', 'subido')")
    )
    op.create_check_constraint(
        "tipo_arqueo", "arqueo", sa.text("tipo IN ('sorpresa', 'programado')")
    )
    op.create_check_constraint(
        "estado_asiento", "asiento", sa.text("estado IN ('registrado', 'anulado')")
    )
    op.create_check_constraint(
        "origen_asiento", "asiento", sa.text("origen IN ('manual', 'automatico')")
    )
    op.create_check_constraint(
        "tipo_linea_asiento", "asiento_linea", sa.text("tipo IN ('debe', 'haber')")
    )
    op.create_check_constraint(
        "motivo_asiento_omitido",
        "asiento_omitido",
        sa.text("motivo IN ('periodo_cerrado', 'sin_cuentas', 'sin_plantilla')"),
    )
    op.create_check_constraint(
        "estado_campana",
        "campana",
        sa.text("estado IN ('brief', 'aprobada', 'en_curso', 'cerrada')"),
    )
    op.create_check_constraint(
        "tipo_campana",
        "campana",
        sa.text("tipo IN ('notoriedad', 'impulso_venta', 'lanzamiento', 'medios', 'evento')"),
    )
    op.execute(
        "UPDATE categoria SET frecuencia_conteo = NULL WHERE frecuencia_conteo IS NOT NULL AND frecuencia_conteo NOT IN ('diario', 'semanal', 'quincenal', 'mensual', 'semestral', 'anual')"
    )
    op.create_check_constraint(
        "frecuencia_conteo",
        "categoria",
        sa.text(
            "frecuencia_conteo IN ('diario', 'semanal', 'quincenal', 'mensual', 'semestral', 'anual')"
        ),
    )
    op.create_check_constraint(
        "custodia_cierre_caja",
        "cierre_caja",
        sa.text("custodia IN ('local_caja_fuerte', 'traslado_contabilidad')"),
    )
    op.execute(
        "UPDATE cierre_caja SET descuadre_atribucion = NULL WHERE descuadre_atribucion IS NOT NULL AND descuadre_atribucion NOT IN ('cajero', 'tercero_reportado', 'encargado')"
    )
    op.create_check_constraint(
        "descuadre_atribucion",
        "cierre_caja",
        sa.text("descuadre_atribucion IN ('cajero', 'tercero_reportado', 'encargado')"),
    )
    op.create_check_constraint(
        "estado_cierre_caja",
        "cierre_caja",
        sa.text("estado IN ('en_proceso', 'conforme', 'con_irregularidad')"),
    )
    op.create_check_constraint(
        "tipo_cliente", "cliente", sa.text("tipo IN ('natural', 'juridico')")
    )
    op.create_check_constraint(
        "direccion_comprobante", "comprobante", sa.text("direccion IN ('emitido', 'recibido')")
    )
    op.create_check_constraint(
        "estado_emision_comprobante",
        "comprobante",
        sa.text("estado_emision IN ('no_aplica', 'pendiente', 'aceptado', 'rechazado', 'error')"),
    )
    op.create_check_constraint(
        "sustento_comprobante",
        "comprobante",
        sa.text(
            "sustento IN ('efectivo', 'voucher_medio_pago', 'movimiento_bancario', 'contrato_credito')"
        ),
    )
    op.create_check_constraint(
        "tipo_comprobante",
        "comprobante",
        sa.text("tipo IN ('boleta', 'factura', 'nc', 'rhe', 'ticket_compra')"),
    )
    op.create_check_constraint(
        "estado_conteo", "conteo", sa.text("estado IN ('abierto', 'cerrado', 'anulado')")
    )
    op.create_check_constraint(
        "tipo_conteo", "conteo", sa.text("tipo IN ('rutina', 'ajuste', 'auditoria')")
    )
    op.create_check_constraint(
        "estado_contrato_laboral",
        "contrato_laboral",
        sa.text("estado IN ('borrador', 'firmado', 'finalizado')"),
    )
    op.create_check_constraint(
        "modalidad_contrato_laboral",
        "contrato_laboral",
        sa.text(
            "modalidad IN ('indeterminado', 'modal_inicio_incremento', 'modal_necesidad_mercado', 'modal_temporada', 'tiempo_parcial', 'jornada_reducida')"
        ),
    )
    op.create_check_constraint(
        "estado_convocatoria",
        "convocatoria",
        sa.text("estado IN ('borrador', 'publicada', 'cerrada')"),
    )
    op.create_check_constraint(
        "motivo_convocatoria",
        "convocatoria",
        sa.text("motivo IN ('reemplazo', 'refuerzo', 'puesto_nuevo')"),
    )
    op.create_check_constraint(
        "tipo_cuenta_contable",
        "cuenta_contable",
        sa.text("tipo IN ('activo', 'pasivo', 'patrimonio', 'ingreso', 'gasto')"),
    )
    op.create_check_constraint("estado_cupon", "cupon", sa.text("estado IN ('activo', 'canjeado')"))
    op.create_check_constraint(
        "estado_custodia_efectivo",
        "custodia_efectivo",
        sa.text("estado IN ('en_caja', 'en_supervisor', 'en_contabilidad', 'disponible')"),
    )
    op.create_check_constraint(
        "resultado_decision_gerencial",
        "decision_gerencial",
        sa.text(
            "resultado IN ('aprobado', 'aprobado_con_condiciones', 'rechazado', 'diferido', 'elevado_a_socios')"
        ),
    )
    op.create_check_constraint(
        "tipo_decision_gerencial",
        "decision_gerencial",
        sa.text("tipo IN ('aprobacion', 'directiva', 'accion_correctiva', 'decision_estrategica')"),
    )
    op.execute(
        "UPDATE devolucion SET destino = NULL WHERE destino IS NOT NULL AND destino NOT IN ('desecho', 'auditoria', 'reintegro')"
    )
    op.create_check_constraint(
        "destino_devolucion",
        "devolucion",
        sa.text("destino IN ('desecho', 'auditoria', 'reintegro')"),
    )
    op.create_check_constraint(
        "estado_devolucion", "devolucion", sa.text("estado IN ('registrada', 'anulada')")
    )
    op.create_check_constraint(
        "motivo_devolucion",
        "devolucion",
        sa.text(
            "motivo IN ('vencido', 'dañado', 'incumplimiento_plazo', 'no_requerido', 'error_solicitud', 'duplicidad')"
        ),
    )
    op.create_check_constraint(
        "origen_devolucion", "devolucion", sa.text("origen IN ('proveedor', 'cliente')")
    )
    op.create_check_constraint(
        "tipo_empresa",
        "empresa",
        sa.text("tipo IN ('operativa', 'logistica', 'servicios', 'asesoria', 'transporte')"),
    )
    op.create_check_constraint(
        "zona_tributaria", "empresa", sa.text("zona_tributaria IN ('amazonia_ley27037', 'general')")
    )
    op.create_check_constraint(
        "tipo_pregunta_encuesta",
        "encuesta_pregunta",
        sa.text("tipo IN ('escala', 'opcion', 'si_no', 'texto')"),
    )
    op.create_check_constraint(
        "canal_encuesta", "encuesta_satisfaccion", sa.text("canal IN ('pos', 'whatsapp', 'link')")
    )
    op.create_check_constraint(
        "estado_encuesta",
        "encuesta_satisfaccion",
        sa.text("estado IN ('enviada', 'respondida', 'expirada')"),
    )
    op.create_check_constraint("canal_entrega", "entrega_reporte", sa.text("canal IN ('bandeja')"))
    op.create_check_constraint(
        "estado_evaluacion_agencia",
        "evaluacion_agencia",
        sa.text("estado IN ('borrador', 'evaluada', 'decidida')"),
    )
    op.create_check_constraint(
        "estado_emision_guia",
        "guia_remision",
        sa.text("estado_emision IN ('pendiente', 'aceptado', 'rechazado', 'error')"),
    )
    op.create_check_constraint(
        "modalidad_traslado_guia", "guia_remision", sa.text("modalidad_traslado IN ('01', '02')")
    )
    op.create_check_constraint(
        "motivo_traslado_guia",
        "guia_remision",
        sa.text("motivo_traslado IN ('01', '04', '13', '18')"),
    )
    op.create_check_constraint(
        "origen_incidencia_inventario",
        "incidencia_inventario",
        sa.text("origen IN ('venta', 'orden_compra', 'orden_produccion')"),
    )
    op.create_check_constraint(
        "tipo_incidencia_inventario",
        "incidencia_inventario",
        sa.text("tipo IN ('sin_almacen', 'sin_sku', 'stock_insuficiente')"),
    )
    op.create_check_constraint(
        "tipo_kds_pantalla", "kds_pantalla", sa.text("tipo IN ('preparacion', 'despacho')")
    )
    op.create_check_constraint(
        "tipo_lead", "lead", sa.text("tipo IN ('contacto', 'visita', 'cupon', 'registro')")
    )
    op.execute(
        "UPDATE lista_precio SET canal = NULL WHERE canal IS NOT NULL AND canal NOT IN ('pdv', 'agente_ia', 'delivery')"
    )
    op.create_check_constraint(
        "canal_lista_precio", "lista_precio", sa.text("canal IN ('pdv', 'agente_ia', 'delivery')")
    )
    op.execute(
        "UPDATE lista_precio SET modalidad = NULL WHERE modalidad IS NOT NULL AND modalidad NOT IN ('mesa', 'takeout', 'delivery')"
    )
    op.create_check_constraint(
        "modalidad_lista_precio",
        "lista_precio",
        sa.text("modalidad IN ('mesa', 'takeout', 'delivery')"),
    )
    op.execute(
        "UPDATE lote SET condicion_almacenamiento = NULL WHERE condicion_almacenamiento IS NOT NULL AND condicion_almacenamiento NOT IN ('refrigerado', 'congelado', 'ambiente')"
    )
    op.create_check_constraint(
        "condicion_almacenamiento",
        "lote",
        sa.text("condicion_almacenamiento IN ('refrigerado', 'congelado', 'ambiente')"),
    )
    op.create_check_constraint(
        "origen_lote",
        "lote",
        sa.text("origen IN ('compra', 'produccion', 'carga_inicial', 'ajuste')"),
    )
    op.create_check_constraint(
        "tipo_marcacion", "marcacion", sa.text("tipo IN ('entrada', 'salida')")
    )
    op.create_check_constraint(
        "direccion_medio_pago", "medio_pago", sa.text("direccion IN ('cobro', 'pago', 'ambos')")
    )
    op.create_check_constraint(
        "tipo_medio_pago",
        "medio_pago",
        sa.text(
            "tipo IN ('efectivo', 'tarjeta_credito', 'tarjeta_debito', 'billetera_digital', 'transferencia', 'cheque', 'credito_empresarial')"
        ),
    )
    op.create_check_constraint(
        "tipo_movimiento_caja", "movimiento_caja", sa.text("tipo IN ('ingreso', 'retiro')")
    )
    op.create_check_constraint(
        "estado_movimiento_dinero",
        "movimiento_dinero",
        sa.text("estado IN ('pendiente', 'ejecutado', 'rechazado')"),
    )
    op.execute(
        "UPDATE movimiento_dinero SET medio_pago = NULL WHERE medio_pago IS NOT NULL AND medio_pago NOT IN ('transferencia', 'cheque', 'efectivo')"
    )
    op.create_check_constraint(
        "medio_pago_movimiento_dinero",
        "movimiento_dinero",
        sa.text("medio_pago IN ('transferencia', 'cheque', 'efectivo')"),
    )
    op.create_check_constraint(
        "tipo_movimiento_dinero", "movimiento_dinero", sa.text("tipo IN ('egreso', 'ingreso')")
    )
    op.execute(
        "UPDATE movimiento_inventario SET motivo_ajuste = NULL WHERE motivo_ajuste IS NOT NULL AND motivo_ajuste NOT IN ('sobrante', 'faltante', 'merma', 'error_registro')"
    )
    op.create_check_constraint(
        "motivo_ajuste",
        "movimiento_inventario",
        sa.text("motivo_ajuste IN ('sobrante', 'faltante', 'merma', 'error_registro')"),
    )
    op.create_check_constraint(
        "tipo_movimiento",
        "movimiento_inventario",
        sa.text(
            "tipo IN ('recepcion_compra', 'transferencia_salida', 'transferencia_entrada', 'consumo_venta', 'consumo_produccion', 'consumo_interno', 'produccion_entrada', 'ajuste', 'devolucion', 'carga_inicial')"
        ),
    )
    op.create_check_constraint(
        "tipo_opcion_agencia", "opcion_agencia", sa.text("tipo IN ('agencia', 'interna')")
    )
    op.create_check_constraint(
        "estado_orden_compra",
        "orden_compra",
        sa.text("estado IN ('borrador', 'emitida', 'recibida_parcial', 'recibida', 'anulada')"),
    )
    op.create_check_constraint(
        "origen_orden_compra", "orden_compra", sa.text("origen IN ('oc', 'directa')")
    )
    op.create_check_constraint(
        "tipo_orden_compra", "orden_compra", sa.text("tipo IN ('insumo', 'activo')")
    )
    op.create_check_constraint(
        "estado_orden_produccion",
        "orden_produccion",
        sa.text(
            "estado IN ('borrador', 'en_proceso', 'conforme', 'no_conforme_reprocesado', 'no_conforme_desechado')"
        ),
    )
    op.create_check_constraint(
        "tipo_capacitacion_pacto",
        "pacto_permanencia",
        sa.text("capacitacion_tipo IN ('curso', 'posgrado', 'diplomado', 'capacitacion')"),
    )
    op.create_check_constraint(
        "estado_pago", "pago", sa.text("estado IN ('pendiente', 'confirmado', 'rechazado')")
    )
    op.create_check_constraint(
        "estado_parametro_empresa",
        "parametro_empresa",
        sa.text("estado IN ('propuesto', 'vigente', 'rechazado', 'reemplazado')"),
    )
    op.create_check_constraint(
        "estado_periodo_contable", "periodo_contable", sa.text("estado IN ('abierto', 'cerrado')")
    )
    op.create_check_constraint(
        "estado_pieza_contenido",
        "pieza_contenido",
        sa.text("estado IN ('planificada', 'publicada', 'descartada')"),
    )
    op.create_check_constraint(
        "estado_pos_tarjeta", "pos_tarjeta", sa.text("estado IN ('operativo', 'averiado', 'baja')")
    )
    op.create_check_constraint(
        "estado_postulante",
        "postulante",
        sa.text(
            "estado IN ('recibido', 'preseleccionado', 'entrevistado', 'verificado', 'oferta_enviada', 'contratado', 'inducido', 'confirmado', 'descartado')"
        ),
    )
    op.create_check_constraint(
        "tipo_promocion",
        "promocion",
        sa.text("tipo IN ('nxm', 'cantidad', 'combo', 'monto_minimo')"),
    )
    op.create_check_constraint(
        "estado_promocion_cupon", "promocion_cupon", sa.text("estado IN ('activa', 'terminada')")
    )
    op.create_check_constraint(
        "clasificacion_proveedor",
        "proveedor",
        sa.text("clasificacion IN ('regular', 'preferente')"),
    )
    op.create_check_constraint(
        "condicion_pago_proveedor", "proveedor", sa.text("condicion_pago IN ('contado', 'credito')")
    )
    op.create_check_constraint(
        "tipo_proveedor", "proveedor", sa.text("tipo IN ('natural', 'juridico')")
    )
    op.create_check_constraint(
        "canal_punto_venta", "punto_venta", sa.text("canal IN ('trabajador', 'web', 'kiosko')")
    )
    op.create_check_constraint(
        "politica_pago_punto_venta",
        "punto_venta",
        sa.text("politica_pago IN ('adelantado', 'al_finalizar')"),
    )
    op.create_check_constraint(
        "tipo_destinatario",
        "regla_destinatario",
        sa.text("tipo IN ('area', 'rol', 'usuario', 'dinamico')"),
    )
    op.create_check_constraint("canal_regla", "regla_distribucion", sa.text("canal IN ('bandeja')"))
    op.create_check_constraint(
        "nivel_regla", "regla_distribucion", sa.text("nivel IN ('info', 'aviso', 'urgente')")
    )
    op.create_check_constraint(
        "nivel_reporte", "reporte_emitido", sa.text("nivel IN ('info', 'aviso', 'urgente')")
    )
    op.create_check_constraint(
        "estado_escalamiento",
        "reporte_escalamiento",
        sa.text("estado IN ('abierto', 'resuelto_supervisor', 'escalado', 'resuelto', 'cerrado')"),
    )
    op.create_check_constraint(
        "motivo_escalamiento",
        "reporte_escalamiento",
        sa.text(
            "motivo IN ('queja', 'demora', 'error_sistema', 'desistimiento_no_resuelto', 'no_conformidad_calidad')"
        ),
    )
    op.create_check_constraint(
        "nivel_escalamiento",
        "reporte_escalamiento",
        sa.text("nivel_actual IN ('supervisor', 'comercial', 'gerencia')"),
    )
    op.create_check_constraint(
        "origen_escalamiento",
        "reporte_escalamiento",
        sa.text("origen IN ('central_pedidos', 'punto_venta', 'produccion')"),
    )
    op.create_check_constraint(
        "estado_reserva",
        "reserva_stock",
        sa.text("estado IN ('activa', 'liberada', 'consumida', 'pendiente_desecho')"),
    )
    op.execute(
        "UPDATE reserva_stock SET motivo = NULL WHERE motivo IS NOT NULL AND motivo NOT IN ('devolucion', 'rechazo_sucursal', 'auditoria')"
    )
    op.create_check_constraint(
        "motivo_reserva_merma",
        "reserva_stock",
        sa.text("motivo IN ('devolucion', 'rechazo_sucursal', 'auditoria')"),
    )
    op.create_check_constraint(
        "tipo_reserva",
        "reserva_stock",
        sa.text("tipo IN ('solicitud', 'produccion', 'merma', 'carrito')"),
    )
    op.create_check_constraint(
        "estado_solicitud",
        "solicitud_insumos",
        sa.text(
            "estado IN ('borrador', 'pendiente', 'aprobada', 'rechazada', 'cancelada', 'despachada', 'recibida')"
        ),
    )
    op.create_check_constraint(
        "estado_solicitud_permiso",
        "solicitud_permiso",
        sa.text("estado IN ('pendiente', 'aprobada', 'rechazada')"),
    )
    op.create_check_constraint(
        "tipo_solicitud_permiso",
        "solicitud_permiso",
        sa.text(
            "tipo IN ('vacaciones', 'licencia_con_goce', 'licencia_sin_goce', 'permiso_horas')"
        ),
    )
    op.create_check_constraint(
        "estado_stock_lote",
        "stock_lote",
        sa.text("estado IN ('disponible', 'bloqueado', 'agotado')"),
    )
    op.create_check_constraint(
        "estado_sucursal", "sucursal", sa.text("estado IN ('activa', 'inactiva')")
    )
    op.create_check_constraint(
        "tenencia_sucursal", "sucursal", sa.text("tenencia IN ('propia', 'alquilada', 'del_grupo')")
    )
    op.create_check_constraint(
        "estado_trabajador", "trabajador", sa.text("estado IN ('activo', 'cesado', 'suspendido')")
    )
    op.execute(
        "UPDATE trabajador SET sistema_pensiones = NULL WHERE sistema_pensiones IS NOT NULL AND sistema_pensiones NOT IN ('onp', 'afp')"
    )
    op.create_check_constraint(
        "sistema_pensiones", "trabajador", sa.text("sistema_pensiones IN ('onp', 'afp')")
    )
    op.create_check_constraint(
        "tipo_vinculo_trabajador",
        "trabajador",
        sa.text("tipo_vinculo IN ('planilla', 'practicante', 'locacion_servicios')"),
    )
    op.create_check_constraint(
        "estado_transferencia", "transferencia", sa.text("estado IN ('en_transito', 'recibida')")
    )
    op.create_check_constraint(
        "preferencia_paleta",
        "usuario",
        sa.text("preferencia_paleta IN ('estandar', 'alto_contraste')"),
    )
    op.create_check_constraint(
        "preferencia_tamano_fuente",
        "usuario",
        sa.text("preferencia_tamano_fuente IN ('estandar', 'grande', 'muy_grande', 'maximo')"),
    )
    op.create_check_constraint(
        "preferencia_tema", "usuario", sa.text("preferencia_tema IN ('claro', 'oscuro')")
    )
    op.create_check_constraint(
        "tipo_usuario", "usuario", sa.text("tipo IN ('humano', 'agente_ia')")
    )
    op.create_check_constraint(
        "canal_venta", "venta", sa.text("canal IN ('pdv', 'agente_ia', 'delivery')")
    )
    op.create_check_constraint(
        "estado_venta",
        "venta",
        sa.text("estado IN ('orden', 'pagada', 'facturada', 'anulada', 'cerrada')"),
    )
    op.create_check_constraint(
        "modalidad_venta", "venta", sa.text("modalidad IN ('mesa', 'takeout', 'delivery')")
    )
    op.execute(
        "UPDATE venta SET descuento_modo = NULL WHERE descuento_modo IS NOT NULL AND descuento_modo NOT IN ('porcentaje', 'monto')"
    )
    op.create_check_constraint(
        "modo_descuento_venta", "venta", sa.text("descuento_modo IN ('porcentaje', 'monto')")
    )
    op.execute(
        "UPDATE venta SET consumo_motivo = NULL WHERE consumo_motivo IS NOT NULL AND consumo_motivo NOT IN ('fin_semana', 'feriado', 'alta_actividad', 'capacitacion', 'otro')"
    )
    op.create_check_constraint(
        "motivo_consumo_personal",
        "venta",
        sa.text(
            "consumo_motivo IN ('fin_semana', 'feriado', 'alta_actividad', 'capacitacion', 'otro')"
        ),
    )
    op.create_check_constraint(
        "tipo_venta", "venta", sa.text("tipo IN ('venta', 'consumo_personal')")
    )
    op.create_check_constraint(
        "estado_preparacion_item",
        "venta_item",
        sa.text("estado_preparacion IN ('pendiente', 'en_preparacion', 'listo', 'entregado')"),
    )


def downgrade() -> None:
    op.drop_constraint("estado_preparacion_item", "venta_item", type_="check")
    op.drop_constraint("tipo_venta", "venta", type_="check")
    op.drop_constraint("motivo_consumo_personal", "venta", type_="check")
    op.drop_constraint("modo_descuento_venta", "venta", type_="check")
    op.drop_constraint("modalidad_venta", "venta", type_="check")
    op.drop_constraint("estado_venta", "venta", type_="check")
    op.drop_constraint("canal_venta", "venta", type_="check")
    op.drop_constraint("tipo_usuario", "usuario", type_="check")
    op.drop_constraint("preferencia_tema", "usuario", type_="check")
    op.drop_constraint("preferencia_tamano_fuente", "usuario", type_="check")
    op.drop_constraint("preferencia_paleta", "usuario", type_="check")
    op.drop_constraint("estado_transferencia", "transferencia", type_="check")
    op.drop_constraint("tipo_vinculo_trabajador", "trabajador", type_="check")
    op.drop_constraint("sistema_pensiones", "trabajador", type_="check")
    op.drop_constraint("estado_trabajador", "trabajador", type_="check")
    op.drop_constraint("tenencia_sucursal", "sucursal", type_="check")
    op.drop_constraint("estado_sucursal", "sucursal", type_="check")
    op.drop_constraint("estado_stock_lote", "stock_lote", type_="check")
    op.drop_constraint("tipo_solicitud_permiso", "solicitud_permiso", type_="check")
    op.drop_constraint("estado_solicitud_permiso", "solicitud_permiso", type_="check")
    op.drop_constraint("estado_solicitud", "solicitud_insumos", type_="check")
    op.drop_constraint("tipo_reserva", "reserva_stock", type_="check")
    op.drop_constraint("motivo_reserva_merma", "reserva_stock", type_="check")
    op.drop_constraint("estado_reserva", "reserva_stock", type_="check")
    op.drop_constraint("origen_escalamiento", "reporte_escalamiento", type_="check")
    op.drop_constraint("nivel_escalamiento", "reporte_escalamiento", type_="check")
    op.drop_constraint("motivo_escalamiento", "reporte_escalamiento", type_="check")
    op.drop_constraint("estado_escalamiento", "reporte_escalamiento", type_="check")
    op.drop_constraint("nivel_reporte", "reporte_emitido", type_="check")
    op.drop_constraint("nivel_regla", "regla_distribucion", type_="check")
    op.drop_constraint("canal_regla", "regla_distribucion", type_="check")
    op.drop_constraint("tipo_destinatario", "regla_destinatario", type_="check")
    op.drop_constraint("politica_pago_punto_venta", "punto_venta", type_="check")
    op.drop_constraint("canal_punto_venta", "punto_venta", type_="check")
    op.drop_constraint("tipo_proveedor", "proveedor", type_="check")
    op.drop_constraint("condicion_pago_proveedor", "proveedor", type_="check")
    op.drop_constraint("clasificacion_proveedor", "proveedor", type_="check")
    op.drop_constraint("estado_promocion_cupon", "promocion_cupon", type_="check")
    op.drop_constraint("tipo_promocion", "promocion", type_="check")
    op.drop_constraint("estado_postulante", "postulante", type_="check")
    op.drop_constraint("estado_pos_tarjeta", "pos_tarjeta", type_="check")
    op.drop_constraint("estado_pieza_contenido", "pieza_contenido", type_="check")
    op.drop_constraint("estado_periodo_contable", "periodo_contable", type_="check")
    op.drop_constraint("estado_parametro_empresa", "parametro_empresa", type_="check")
    op.drop_constraint("estado_pago", "pago", type_="check")
    op.drop_constraint("tipo_capacitacion_pacto", "pacto_permanencia", type_="check")
    op.drop_constraint("estado_orden_produccion", "orden_produccion", type_="check")
    op.drop_constraint("tipo_orden_compra", "orden_compra", type_="check")
    op.drop_constraint("origen_orden_compra", "orden_compra", type_="check")
    op.drop_constraint("estado_orden_compra", "orden_compra", type_="check")
    op.drop_constraint("tipo_opcion_agencia", "opcion_agencia", type_="check")
    op.drop_constraint("tipo_movimiento", "movimiento_inventario", type_="check")
    op.drop_constraint("motivo_ajuste", "movimiento_inventario", type_="check")
    op.drop_constraint("tipo_movimiento_dinero", "movimiento_dinero", type_="check")
    op.drop_constraint("medio_pago_movimiento_dinero", "movimiento_dinero", type_="check")
    op.drop_constraint("estado_movimiento_dinero", "movimiento_dinero", type_="check")
    op.drop_constraint("tipo_movimiento_caja", "movimiento_caja", type_="check")
    op.drop_constraint("tipo_medio_pago", "medio_pago", type_="check")
    op.drop_constraint("direccion_medio_pago", "medio_pago", type_="check")
    op.drop_constraint("tipo_marcacion", "marcacion", type_="check")
    op.drop_constraint("origen_lote", "lote", type_="check")
    op.drop_constraint("condicion_almacenamiento", "lote", type_="check")
    op.drop_constraint("modalidad_lista_precio", "lista_precio", type_="check")
    op.drop_constraint("canal_lista_precio", "lista_precio", type_="check")
    op.drop_constraint("tipo_lead", "lead", type_="check")
    op.drop_constraint("tipo_kds_pantalla", "kds_pantalla", type_="check")
    op.drop_constraint("tipo_incidencia_inventario", "incidencia_inventario", type_="check")
    op.drop_constraint("origen_incidencia_inventario", "incidencia_inventario", type_="check")
    op.drop_constraint("motivo_traslado_guia", "guia_remision", type_="check")
    op.drop_constraint("modalidad_traslado_guia", "guia_remision", type_="check")
    op.drop_constraint("estado_emision_guia", "guia_remision", type_="check")
    op.drop_constraint("estado_evaluacion_agencia", "evaluacion_agencia", type_="check")
    op.drop_constraint("canal_entrega", "entrega_reporte", type_="check")
    op.drop_constraint("estado_encuesta", "encuesta_satisfaccion", type_="check")
    op.drop_constraint("canal_encuesta", "encuesta_satisfaccion", type_="check")
    op.drop_constraint("tipo_pregunta_encuesta", "encuesta_pregunta", type_="check")
    op.drop_constraint("zona_tributaria", "empresa", type_="check")
    op.drop_constraint("tipo_empresa", "empresa", type_="check")
    op.drop_constraint("origen_devolucion", "devolucion", type_="check")
    op.drop_constraint("motivo_devolucion", "devolucion", type_="check")
    op.drop_constraint("estado_devolucion", "devolucion", type_="check")
    op.drop_constraint("destino_devolucion", "devolucion", type_="check")
    op.drop_constraint("tipo_decision_gerencial", "decision_gerencial", type_="check")
    op.drop_constraint("resultado_decision_gerencial", "decision_gerencial", type_="check")
    op.drop_constraint("estado_custodia_efectivo", "custodia_efectivo", type_="check")
    op.drop_constraint("estado_cupon", "cupon", type_="check")
    op.drop_constraint("tipo_cuenta_contable", "cuenta_contable", type_="check")
    op.drop_constraint("motivo_convocatoria", "convocatoria", type_="check")
    op.drop_constraint("estado_convocatoria", "convocatoria", type_="check")
    op.drop_constraint("modalidad_contrato_laboral", "contrato_laboral", type_="check")
    op.drop_constraint("estado_contrato_laboral", "contrato_laboral", type_="check")
    op.drop_constraint("tipo_conteo", "conteo", type_="check")
    op.drop_constraint("estado_conteo", "conteo", type_="check")
    op.drop_constraint("tipo_comprobante", "comprobante", type_="check")
    op.drop_constraint("sustento_comprobante", "comprobante", type_="check")
    op.drop_constraint("estado_emision_comprobante", "comprobante", type_="check")
    op.drop_constraint("direccion_comprobante", "comprobante", type_="check")
    op.drop_constraint("tipo_cliente", "cliente", type_="check")
    op.drop_constraint("estado_cierre_caja", "cierre_caja", type_="check")
    op.drop_constraint("descuadre_atribucion", "cierre_caja", type_="check")
    op.drop_constraint("custodia_cierre_caja", "cierre_caja", type_="check")
    op.drop_constraint("frecuencia_conteo", "categoria", type_="check")
    op.drop_constraint("tipo_campana", "campana", type_="check")
    op.drop_constraint("estado_campana", "campana", type_="check")
    op.drop_constraint("motivo_asiento_omitido", "asiento_omitido", type_="check")
    op.drop_constraint("tipo_linea_asiento", "asiento_linea", type_="check")
    op.drop_constraint("origen_asiento", "asiento", type_="check")
    op.drop_constraint("estado_asiento", "asiento", type_="check")
    op.drop_constraint("tipo_arqueo", "arqueo", type_="check")
    op.drop_constraint("origen_archivo", "archivo", type_="check")
    op.drop_constraint("tipo_amonestacion", "amonestacion", type_="check")
    op.drop_constraint("motivo_ajuste", "ajuste", type_="check")
    op.drop_constraint("estado_ajuste", "ajuste", type_="check")
    op.drop_constraint("tipo_acta", "acta", type_="check")
