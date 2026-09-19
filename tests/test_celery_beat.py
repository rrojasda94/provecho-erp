"""El programador periódico está bien cableado.

Un nombre mal escrito en `beat_schedule` no falla en ningún lado: beat
encola una tarea que nadie registró, el worker la descarta, y el barrido
simplemente no ocurre nunca. Es el modo de falla más silencioso del ERP —
justamente en las tareas que existen para que algo no pase inadvertido.
"""

from src.core.celery_app import celery_app

ESPERADAS = {
    "sales.barrer_pedidos_demorados",
    "sales.barrer_comprobantes_pendientes",
    "inventory.bloquear_lotes_vencidos",
    "inventory.reportar_conteos_vencidos",
    "marketing.barrer_encuestas_vencidas",
    "production.generar_reportes_de_jornada_vencidos",
    "assets.barrer_vencimientos",
    "accounting.correr_depreciacion_mensual",
    "core.latido_worker",
}


def test_toda_tarea_programada_existe_de_verdad() -> None:
    # Lo mismo que hace el worker al arrancar: cargar `include`. Así el test
    # cubre los dos errores, el nombre mal escrito en el schedule y el módulo
    # de tareas que nadie agregó a `include`.
    celery_app.loader.import_default_modules()
    programadas = {
        entrada["task"] for entrada in celery_app.conf.beat_schedule.values()
    }
    assert programadas <= set(celery_app.tasks), (
        f"programadas sin registrar: {programadas - set(celery_app.tasks)}"
    )


def test_los_barridos_siguen_programados() -> None:
    """Que la tarea exista no alcanza: sacarla del schedule la deja escrita
    y sin correr, que es la forma en que estas deudas se reabren solas."""
    programadas = {
        entrada["task"] for entrada in celery_app.conf.beat_schedule.values()
    }
    assert ESPERADAS <= programadas


def test_encolar_con_redis_caido_falla_rapido_tambien_en_el_backend_de_resultados():
    """`apply_async(retry=False)` solo apaga los reintentos del broker: el
    backend de resultados es otra conexión con su propia política (20
    reintentos por defecto), y con Redis caído dejaba colgado al request que
    confirmaba una venta. Sin este tope, el e2e del sitio pasaba o no según
    cuánto tardara Redis en negarse."""
    from src.core.celery_app import celery_app

    politica = celery_app.conf.result_backend_transport_options["retry_policy"]
    assert politica["max_retries"] <= 1
    assert celery_app.conf.redis_socket_connect_timeout <= 1
