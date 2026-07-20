# Provecho ERP — Índice de documentación

ERP modular para el grupo gastronómico Provecho: una empresa, varias marcas
(Charlie's, Ariana, La Avenida, ...), varios locales y un almacén central.
Webapp + app Android (15+). Agentes humanos y de IA toman pedidos.

**Fase actual: F0 — Fundaciones** (scaffold, arquitectura, contratos, docs).

## Cómo está organizada

Documentos agrupados por tema (sin numeración global — insertar uno nuevo no
renumera nada). Este archivo define el orden de lectura recomendado.

### Orden de lectura recomendado

1. [foundation/business-philosophy.md](foundation/business-philosophy.md) — principios invariantes
2. [foundation/vision.md](foundation/vision.md) — visión y modelo de negocio
3. [foundation/glossary.md](foundation/glossary.md) — terminología oficial (lenguaje ubicuo)
4. [architecture/overview.md](architecture/overview.md) — arquitectura
5. [domain/domain-model.md](domain/domain-model.md) — entidades y relaciones
6. [domain/business-rules.md](domain/business-rules.md) — reglas de negocio
7. [engineering/engineering-guide.md](engineering/engineering-guide.md) — cómo construir

### Mapa completo

| Carpeta | Documento | Contenido |
|---------|-----------|-----------|
| **foundation/** | [business-philosophy.md](foundation/business-philosophy.md) | Principios invariantes ("constitución") |
| | [vision.md](foundation/vision.md) | Visión y modelo de negocio |
| | [glossary.md](foundation/glossary.md) | Lenguaje ubicuo — terminología oficial |
| **domain/** | [domain-model.md](domain/domain-model.md) | Entidades y relaciones |
| | [business-rules.md](domain/business-rules.md) | Validaciones, cálculos, políticas |
| | [workflows.md](domain/workflows.md) | Flujos operativos |
| | [process-nomenclature.md](domain/process-nomenclature.md) | Nomenclatura y versionado de procesos (`PROC-<área>-nnn`) |
| | [use-cases.md](domain/use-cases.md) | Casos de uso concretos por proceso |
| | [state-machines.md](domain/state-machines.md) | Ciclos de vida de entidades |
| **architecture/** | [overview.md](architecture/overview.md) | Modular monolith, Clean Arch, DDD |
| | [tech-stack.md](architecture/tech-stack.md) | Stack y justificación |
| | [data-model.md](architecture/data-model.md) | Modelo de datos (tablas, ERD) |
| | [events.md](architecture/events.md) | Catálogo de eventos internos |
| | [adr/](architecture/adr/) | Decisiones de arquitectura |
| **engineering/** | [engineering-guide.md](engineering/engineering-guide.md) | Guía principal para constructores (humano + IA) |
| | [coding-standards.md](engineering/coding-standards.md) | Convenciones, formato, linters |
| | [api-guidelines.md](engineering/api-guidelines.md) | Convenciones de API REST |
| | [testing.md](engineering/testing.md) | Estrategia de pruebas |
| | [devops.md](engineering/devops.md) | Docker, entornos, CI/CD, observabilidad |
| **security/** | [security.md](security/security.md) | Autenticación, hardening, auditoría, backups |
| | [authorization.md](security/authorization.md) | RBAC, roles, permisos, restricciones tenant |
| **product/** | [modules.md](product/modules.md) | Índice de módulos → specs en `src/modules/*/README.md` |
| | [ui-ux.md](product/ui-ux.md) | Branding y reglas de UX |
| **templates/** | [templates/rrhh/](templates/rrhh/) | Plantillas rellenables de documentos (RRHH: memorándum, certificado, amonestación, acta, permiso, pacto de permanencia, contratos, convocatoria, entrevista, oferta, alta, uniforme) — requieren visado legal |
| | [templates/compras/](templates/compras/) | Plantillas de Compras (ficha de proveedor, RFQ, orden de compra, evaluación) |
| | [templates/comercial/](templates/comercial/) | Plantillas de Comercial (precio/margen, brief de promoción, nuevo producto, desempeño, capacitación) |
| | [templates/almacen-logistica/](templates/almacen-logistica/) | Plantillas de Almacén-Logística (conteo, ajuste, merma, transferencia, devolución, hoja de ruta) |
| **rrhh/** | [rrhh/](rrhh/) | Área de RRHH: marco legal laboral (régimen microempresa REMYPE), perfiles de puesto, flujo completo de incorporación |
| **compras/** | [compras/](compras/) | Área de Compras: marco legal-tributario (régimen Amazonía, SPOT, comprobantes), perfil de encargado de compras, flujo de abastecimiento |
| **comercial/** | [comercial/](comercial/) | Área Comercial: política de precio/margen/promociones/metas, perfil de jefe comercial, coordinación con Marketing y Producción/I+D+i |
| **almacen-logistica/** | [almacen-logistica/](almacen-logistica/) | Área Almacén y Logística: FEFO/FIFO, conteo/ajuste, vencimientos/merma, transferencias/transporte, perfiles de almacén y chofer |
| **diagrams/** | [diagrams/](diagrams/) | Diagramas Mermaid transversales; [Procesos/](diagrams/Procesos/) tiene los SOPs por área (Operaciones, Comercial, Contabilidad, Ventas, Logística-Almacén, Recursos-Humanos, Compras) — carpeta física `Logistica-Almacen/`, área de negocio "Almacén y Logística" |
| **prompts/** | [prompts/](prompts/) | Guías de contexto por área para agentes de IA |

## Fuentes de verdad en la raíz del repo

- [`/CLAUDE.md`](../CLAUDE.md) — contrato operativo que la IA carga cada sesión
  (resume y apunta a `engineering/engineering-guide.md`).
- [`/ROADMAP.md`](../ROADMAP.md) — bitácora viva de lo construido y pendiente.
- [`/CHANGELOG.md`](../CHANGELOG.md) — historial de cambios (SemVer).

## Arranque rápido

```bash
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000/docs — Web: http://localhost:3000
