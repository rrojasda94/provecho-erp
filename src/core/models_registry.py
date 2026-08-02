"""Registro de modelos: importa todos los modelos para poblar Base.metadata.

Lo usan Alembic (autogenerate) y los tests. Cada módulo nuevo agrega aquí
su import de `infrastructure.models`.
"""

import src.core.sync.models  # noqa: F401
import src.modules.accounting.infrastructure.models  # noqa: F401
import src.modules.inventory.infrastructure.models  # noqa: F401
import src.modules.marketing.infrastructure.models  # noqa: F401
import src.modules.production.infrastructure.models  # noqa: F401
import src.modules.purchases.infrastructure.models  # noqa: F401
import src.modules.rrhh.infrastructure.models  # noqa: F401
import src.modules.sales.infrastructure.models  # noqa: F401
import src.modules.users.infrastructure.models  # noqa: F401
import src.shared.models  # noqa: F401
