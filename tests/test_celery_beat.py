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
