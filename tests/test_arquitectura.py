"""Los límites entre capas y módulos, como test.

Las reglas de CLAUDE.md se cumplen hoy; lo que faltaba era algo que avisara
cuando dejen de cumplirse. Un import equivocado no rompe ningún test
funcional: aparece meses después como un módulo que ya no se puede sacar.

Cada excepción de `_EXCEPCIONES_CRUZADAS` está ahí porque existe hoy y
sacarla cuesta más de lo que rinde ahora (ver
`docs/architecture/audit-2026-08-01.md`). La lista puede encogerse, nunca
crecer sin una decisión explícita.
"""

import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
MODULOS = sorted(p.name for p in (SRC / "modules").iterdir() if (p / "__init__.py").exists())

# Infraestructura que el dominio no puede tocar: si necesita cualquiera de
# estas, la regla dejó de ser pura y el test dejó de poder ejecutarse solo.
_PROHIBIDO_EN_DOMAIN = ("fastapi", "sqlalchemy", "pydantic", "httpx", "redis", "celery")

# Superficie pública de un módulo: lo único importable desde otro.
_CONTRATOS_PUBLICOS = ("api.deps", "application.queries_publicas")

# Acoplamientos que ya existen y que el informe de auditoría difiere en vez
# de resolver. Clave: módulo que importa. Valor: prefijos que puede importar.
_EXCEPCIONES_CRUZADAS = {
    # `Empresa`/`Sucursal`/`Almacen`/`Persona` son organización transversal
    # (data-model §1) y viven en users por historia, no por diseño. Moverlas
    # a `shared/models` toca 37 archivos: diferido, no descartado.
    "*": ("users.infrastructure.models",),
    # `Articulo`/`Receta` del catálogo: purchases y production los leen para
    # validar la línea de la orden. Pide un contrato público de inventory.
    "purchases": ("inventory.infrastructure.models",),
    "production": ("inventory.infrastructure.models",),
    # Caja compone el resumen de ventas del día.
    # `autorizacion.verificar`/`TokenInvalido` son la elevación de PIN de
    # supervisor (RN-AUD-005): caja y PDV la necesitan en el mismo request
    # que negocia el permiso, no como notificación async. Pide un contrato
    # público de `users` para la verificación de PIN puntual.
    "accounting": ("sales.application.queries_publicas", "users.application"),
    # `precios.py` lee `Categoria` de inventory para resolver la carta por
    # categoría (deuda anterior a este test, no introducida acá).
    "sales": ("users.application", "inventory.infrastructure.models.categoria"),
    # `privacidad.anonimizar_postulante` reusa el mismo candado de PIN que
    # `personas.anonimizar` (ADR-011): mismo custodio, misma verificación,
    # otra tabla. Pide el mismo contrato público que falta arriba.
    "rrhh": ("users.infrastructure.repositories",),
}


def _imports(archivo: pathlib.Path) -> list[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    nombres: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres += [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            nombres.append(nodo.module)
    return nombres


def _archivos(*partes: str) -> list[pathlib.Path]:
    return sorted((SRC / "modules").glob("/".join(("*",) + partes)))


@pytest.mark.parametrize("archivo", _archivos("domain", "*.py"), ids=str)
def test_domain_no_conoce_infraestructura(archivo: pathlib.Path) -> None:
    """El dominio son reglas puras: sin ORM, sin framework web, sin red."""
    malos = [
        i for i in _imports(archivo)
        if i.split(".")[0] in _PROHIBIDO_EN_DOMAIN
    ]
    assert not malos, f"{archivo} importa infraestructura: {malos}"


@pytest.mark.parametrize("archivo", _archivos("domain", "*.py"), ids=str)
def test_domain_no_conoce_ni_core_ni_otros_modulos(archivo: pathlib.Path) -> None:
    malos = [
        i for i in _imports(archivo)
        if i.startswith(("src.core", "src.shared", "src.modules"))
    ]
    assert not malos, f"{archivo} debería depender solo de la stdlib: {malos}"


@pytest.mark.parametrize("archivo", _archivos("application", "*.py"), ids=str)
def test_application_no_conoce_fastapi(archivo: pathlib.Path) -> None:
    """El caso de uso se prueba sin levantar la API; si importa FastAPI, ya
    no."""
    malos = [i for i in _imports(archivo) if i.split(".")[0] == "fastapi"]
    assert not malos, f"{archivo} importa FastAPI: {malos}"


@pytest.mark.parametrize("modulo", MODULOS)
def test_modulo_solo_entra_a_otro_por_su_contrato_publico(modulo: str) -> None:
    """Los módulos se hablan por eventos o por contrato público. Nunca por
    el dominio del otro, y nunca por sus repositorios."""
    permitido = _EXCEPCIONES_CRUZADAS["*"] + _EXCEPCIONES_CRUZADAS.get(modulo, ())
    violaciones = []
    for archivo in sorted((SRC / "modules" / modulo).rglob("*.py")):
        for imp in _imports(archivo):
            if not imp.startswith("src.modules."):
                continue
            resto = imp[len("src.modules."):]
            ajeno = resto.split(".")[0]
            if ajeno == modulo:
                continue
            camino = resto[len(ajeno) + 1:]
            if camino.startswith(_CONTRATOS_PUBLICOS):
                continue
            if any(resto.startswith(p) for p in permitido):
                continue
            violaciones.append(f"{archivo.relative_to(SRC)} → {imp}")
    assert not violaciones, (
        f"{modulo} entra a otro módulo por fuera de su contrato público:\n"
        + "\n".join(violaciones)
    )


@pytest.mark.parametrize("modulo", MODULOS)
def test_ningun_modulo_importa_el_dominio_de_otro(modulo: str) -> None:
    """La regla más dura de CLAUDE.md, sin excepciones declaradas."""
    violaciones = [
        f"{archivo.relative_to(SRC)} → {imp}"
        for archivo in sorted((SRC / "modules" / modulo).rglob("*.py"))
        for imp in _imports(archivo)
        if imp.startswith("src.modules.")
        and ".domain" in imp
        and not imp.startswith(f"src.modules.{modulo}.")
    ]
    assert not violaciones, "\n".join(violaciones)


def test_core_no_importa_el_dominio_de_ningun_modulo() -> None:
    """`core` ensambla la app y puede tocar routers y contratos públicos;
    las reglas de negocio de un módulo no son asunto suyo."""
    violaciones = [
        f"{archivo.relative_to(SRC)} → {imp}"
        for archivo in sorted((SRC / "core").rglob("*.py"))
        for imp in _imports(archivo)
        if ".domain" in imp and imp.startswith("src.modules.")
    ]
    assert not violaciones, "\n".join(violaciones)


def test_shared_no_depende_de_ningun_modulo() -> None:
    """`shared` está debajo de todos: si mira hacia arriba, deja de ser
    reutilizable y se vuelve un módulo más."""
    violaciones = [
        f"{archivo.relative_to(SRC)} → {imp}"
        for archivo in sorted((SRC / "shared").rglob("*.py"))
        for imp in _imports(archivo)
        if imp.startswith("src.modules.")
    ]
    assert not violaciones, "\n".join(violaciones)
