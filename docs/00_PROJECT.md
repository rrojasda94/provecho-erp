# Provecho ERP — Índice de documentación

**Provecho** es el ERP (el producto de software). **Grupo Majambo** es el
grupo empresarial gastronómico que lo usa: una empresa, varias marcas
(Charlie's, Ariana, La Avenida, ...), varios locales y un almacén central.
No confundir los dos nombres.
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
| | [F1.docx](foundation/F1.docx) | Brief original del ERP dictado por el usuario — material fuente del que salieron los tres documentos de arriba. Se conserva por trazabilidad; **no es normativo**: ante una diferencia mandan `glossary.md` y `vision.md` |
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
| | [audit-2026-08-01.md](architecture/audit-2026-08-01.md) | Auditoría arquitectónica: riesgos priorizados, qué se aplicó y qué se descartó |
| | [adr/](architecture/adr/) | Decisiones de arquitectura — 001 modular monolith, 002 stack, 003 Izipay, 004 tenant, 005 Factiliza, 006 observabilidad, 007 backups y salud, 008 entrega continua, 009 modo offline del PDV, 010 contrato OpenAPI, 011 derechos ARCO, 012 dashboard + caja, 013 arquitectura frontend, 014 parámetros configurables por empresa, 015 lote y FEFO, 016 eventos post-commit, 017 jerarquía de errores compartida, 018 cobro dividido/mesa/descuento de orden, 019 conteo cíclico por categoría, 020 reserva/solicitud/transferencia, 021 atribución lead→venta y dueño de la encuesta, 022 restricciones de permiso, 023 variantes de producto y recetas en la ficha, 024 catálogo cerrado de reportes, 025 ciclo de caja completo, 026 paginación de colecciones, 027 guía de remisión, 028 merma como reserva y devolución, 029 encuesta por nodos y canal WhatsApp, 030 evaluación de agencia y acumulado de campaña, 031 audit_log transversal, 032 token de API para agentes, 033 módulo reports (emisión y distribución), 034 consumo de personal, 035 restas y lienzo de nodos de receta, 036 escalamiento de reportes y destinos accionables, 037 sistema visual, modo oscuro y accesibilidad, 038 grupos de opciones por variante en la carta, 039 rastro jerárquico y "volver" histórico, 040 abastecedor de respaldo, 041 reseteo de PIN y consulta de documento, 042 la variante hereda del padre, 043 orden abierta y ventana de corrección, 044 cadena de estaciones del KDS, 045 pinpad y bloqueo de pantalla del PDV, 046 carga masiva de recetas en dos fases, 047 dos suites de Playwright (`e2e` con techo, `uso` sin él), 048 el proxy del navegador pasa bytes, no texto, 049 la caja la abre el cajero (enmienda ADR-025), 050 el login también se teclea en el pinpad (enmienda ADR-045), 051 el requerimiento de la jornada, 052 exportar es la plantilla llena y la columna `ID` es la identidad, 053 la dirección se elige en el mapa, 054 el delivery se cobra por kilómetro, 055 atributos y variantes generadas (modelo Odoo), 056 líneas de receta condicionadas por variante y con UdM propia |
| **engineering/** | [engineering-guide.md](engineering/engineering-guide.md) | Guía principal para constructores (humano + IA) |
| | [module-guide.md](engineering/module-guide.md) | Cómo crear un módulo: estructura, los 7 registros para activarlo, módulo de referencia |
| | [trabajo-en-paralelo.md](engineering/trabajo-en-paralelo.md) | Varias ramas a la vez sin duplicar trabajo: PR en borrador desde el primer commit, y quién renumera cuando dos ramas piden el mismo ADR o la misma cabeza de Alembic |
| | [coding-standards.md](engineering/coding-standards.md) | Convenciones, formato, linters |
| | [api-guidelines.md](engineering/api-guidelines.md) | Convenciones de API REST |
| | [testing-strategy.md](engineering/testing-strategy.md) | Qué se prueba y en qué nivel; por qué el hueco real era el contrato cliente↔servidor y no el e2e |
| | [testing.md](engineering/testing.md) | Estrategia de pruebas |
| | [devops.md](engineering/devops.md) | Docker, entornos, CI/CD, despliegue |
| | [observabilidad.md](engineering/observabilidad.md) | GlitchTip (errores), Loki (logs), salud y monitor |
| | [integraciones-google.md](engineering/integraciones-google.md) | Google Maps: las dos claves (navegador y servidor), cómo obtenerlas y restringirlas, y qué se apaga si faltan |
| **security/** | [security.md](security/security.md) | Autenticación, hardening, auditoría, backups |
| | [authorization.md](security/authorization.md) | RBAC, roles, permisos, restricciones tenant |
| | [proteccion-datos-personales.md](security/proteccion-datos-personales.md) | Ley 29733: qué datos, derechos ARCO, retención, brecha |
| **product/** | [modules.md](product/modules.md) | Índice de módulos → specs en `src/modules/*/README.md` |
| | [ui-ux.md](product/ui-ux.md) | Branding y reglas de UX |
| | [frontend-architecture.md](product/frontend-architecture.md) | F2 — arquitectura de frontend (tokens, componentes, layout, estado, tablas, permisos visuales...), estado por sección y qué falta cerrar antes del alfa |
| **templates/** | [templates/rrhh/](templates/rrhh/) | Plantillas rellenables de documentos (RRHH: memorándum, certificado, amonestación, acta, permiso, pacto de permanencia, contratos, convocatoria, entrevista, oferta, alta, uniforme) — requieren visado legal |
| | [templates/compras/](templates/compras/) | Plantillas de Compras (ficha de proveedor, RFQ, orden de compra, evaluación) |
| | [templates/comercial/](templates/comercial/) | Plantillas de Comercial (precio/margen, brief de promoción, nuevo producto, desempeño, capacitación) |
| | [templates/almacen-logistica/](templates/almacen-logistica/) | Plantillas de Almacén-Logística (conteo, ajuste, merma, transferencia, devolución, hoja de ruta) |
| | [templates/produccion/](templates/produccion/) | Plantillas de Producción (orden de producción, reporte de producción, no conformidad, checklist de inocuidad, conteo de cocina) |
| | [templates/gerencia/](templates/gerencia/) | Plantillas de Gerencia (acta de decisión gerencial, evaluación de nuevo mercado/marca) |
| | [templates/marketing/](templates/marketing/) | Plantillas de Marketing (brief de campaña, calendario de contenido, evaluación de propuesta de agencia, checklist de material en sucursal) |
| | [templates/contabilidad/](templates/contabilidad/) | Plantillas de Contabilidad (arqueo de caja, conciliación bancaria, orden de pago, flujo de caja semanal) |
| **rrhh/** | [rrhh/](rrhh/) | Área de RRHH: marco legal laboral (régimen microempresa REMYPE), perfiles de puesto, flujo completo de incorporación |
| **compras/** | [compras/](compras/) | Área de Compras: marco legal-tributario (régimen Amazonía, SPOT, comprobantes), perfil de encargado de compras, flujo de abastecimiento |
| **comercial/** | [comercial/](comercial/) | Área Comercial: política de precio/margen/promociones/metas, perfil de jefe comercial, coordinación con Marketing y Producción/I+D+i |
| **almacen-logistica/** | [almacen-logistica/](almacen-logistica/) | Área Almacén y Logística: FEFO/FIFO, conteo/ajuste, vencimientos/merma, transferencias/transporte, perfiles de almacén y chofer |
| **produccion/** | [produccion/](produccion/) | Área Producción (spec a futuro, cocina 2027): cronograma, control de calidad/no conformidad, inocuidad, inventario de cocina, soporte a I+D+i, perfiles de jefe de cocina y cocinero |
| **gerencia/** | [gerencia/](gerencia/) | Área Gerencia: gobierno corporativo, matriz de aprobaciones (fuente única de umbrales), dirección estratégica, supervisión/control, perfil de Gerente General |
| **marketing/** | [marketing/](marketing/) | Área Marketing: uso de marca/naming, contenido pertinente, campañas (lanzamiento/medios/eventos), material en sucursal, agencias; frontera con Comercial (atrae leads vs. cierra) |
| **contabilidad/** | [contabilidad/](contabilidad/) | Área Contabilidad (tesorería + finanzas + registro en un solo responsable, supervisada por Gerencia): política de segregación/control, marco tributario PE, perfil de contador/tesorero, SOPs de pago/conciliación/arqueo |
| **diagrams/** | [diagrams/](diagrams/) | Diagramas Mermaid transversales; [Procesos/](diagrams/Procesos/) tiene los SOPs y BPMN por área (Operaciones, Comercial, Contabilidad, Logística-Almacén, Recursos-Humanos, Compras, Producción, Marketing) — carpeta física `Logistica-Almacen/`, área de negocio "Almacén y Logística"; la venta vive en `Comercial/` |
| **prompts/** | [prompts/](prompts/) | Guías de contexto por área para agentes de IA |

## Fuentes de verdad en la raíz del repo

- [`/CLAUDE.md`](../CLAUDE.md) — contrato operativo que la IA carga cada sesión
  (resume y apunta a `engineering/engineering-guide.md`).
- [`/ROADMAP.md`](../ROADMAP.md) — bitácora viva de lo construido y pendiente.
  La deuda técnica cuelga de [`roadmap/deuda/`](roadmap/deuda/), un archivo
  por área.
- [`/CHANGELOG.md`](../CHANGELOG.md) — historial de cambios (SemVer).

## Arranque rápido

```bash
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000/docs — Web: http://localhost:3000

Ese compose es **solo desarrollo**; el servidor usa `docker-compose.prod.yml`
(ver [engineering/devops.md](engineering/devops.md#despliegue)).
