# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).
Versionado: [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Added

- Branding Provecho aplicado: paleta, tipografías (Anton Italic + Inter) y
  tokens CSS (`docs/product/ui-ux.md`).
- ADR 0003: Izipay como pasarela de pago.
- `PROC-COM-002` Cobro y Emisión de Comprobante de Pago v1.0: narrativa +
  Mermaid en `docs/domain/workflows.md`, diagrama BPMN 2.0 en
  `docs/diagrams/Procesos/Comercial/PROC-COM-002-v1.0.bpmn` (detalle del
  paso "cobro" de `PROC-COM-001`, RN-COM-005).
- `PROC-CTB-002` Apertura de caja v1.0: narrativa + Mermaid en
  `docs/domain/workflows.md`, diagrama BPMN 2.0 en
  `docs/diagrams/Procesos/Contabilidad/PROC-CTB-002-v1.0.bpmn`. Nuevas
  reglas RN-POS-009 a RN-POS-013 y RN-MDP-006.
- `PROC-OPE-001` Apertura de sucursal v1.0: nueva área `OPE` (Operaciones)
  en `process-nomenclature.md`; narrativa + Mermaid en
  `docs/domain/workflows.md`, diagrama BPMN 2.0 en
  `docs/diagrams/Procesos/Operaciones/PROC-OPE-001-v1.0.bpmn` (checklist
  físico de apertura, recepción de pedido, limpieza, apertura de caja
  referenciada). Nuevas reglas RN-SUC-006 a RN-SUC-012, RN-PER-006 y
  RN-RRHH-009 a RN-RRHH-011. Glosario: agrega "Supervisor" (Actores) y
  "Alarma" (Recursos).
- SOPs de limpieza (14) y de lavado de menaje en
  `docs/diagrams/Procesos/Operaciones/Limpieza/`.
- SOPs de procesos comerciales/caja/apertura (9) derivados de los BPMN
  vigentes, en `Comercial/Ventas/`, `Comercial/Cobros/`,
  `Contabilidad/Caja/` y `Operaciones/Apertura-Sucursal/`.
- SOPs de `PROC-INV-001` (3): conteo de insumos y envío de requerimiento,
  picking y despacho en almacén central, recepción y devoluciones en
  local — nueva área `Logistica-Almacen` en
  `docs/diagrams/Procesos/`.

### Changed

- `PROC-INV-001` Abastecimiento de locales v0.1 → v0.2: detalla el conteo
  de fin de jornada en sucursal (balanzas, lector QR, ventana de 5 min
  fuera de refrigeración, alerta por margen de error RN-INV-015, cálculo
  de sugerido por punto de reorden RN-INV-013). Sigue en Borrador —
  picking/packing/transporte en almacén central aún sin este nivel de
  detalle.
- `PROC-CTB-001` Cierre de caja v1.0 → v1.1: agrega la bifurcación de
  custodia del fondo/caja chica (local en sucursal vs. traslado a
  oficinas de contabilidad, RN-MDP-006); RN-MDP-002 ampliada para cubrir
  la cadena de custodia en sentido inverso (apertura). Máquina de estados
  "Custodia de efectivo" actualizada en `docs/domain/state-machines.md`.
- Referencias a Mercadopago eliminadas (decisión: Izipay).
- Docs reorganizados por tema (`foundation/`, `domain/`, `architecture/`,
  `engineering/`, `security/`, `product/`) en vez de numeración plana;
  índice y orden de lectura en `docs/00_PROJECT.md`.
- Nuevos documentos de conocimiento: glosario (lenguaje ubicuo), filosofía del
  negocio, reglas de negocio (separadas del modelo de dominio), catálogo de
  eventos, máquinas de estado, autorización (RBAC, separada de seguridad).
- `AI_RULES` → `engineering/engineering-guide.md` (guía extensa; `/CLAUDE.md`
  la resume y apunta a ella).

## [0.1.0] - 2026-07-04

### Added

- Scaffold inicial: modular monolith (FastAPI + Next.js + PostgreSQL).
- Core: app factory, settings por entorno, sesión SQLAlchemy, event bus interno.
- Endpoint `/health` con tests.
- Especificaciones (contratos) de módulos: users, inventory, sales, purchases, accounting.
- Documentación: arquitectura, ADRs, modelo de negocio, modelo de datos v1.
- Docker Compose (api, web, postgres, redis), CI con GitHub Actions.
- Reglas de desarrollo en `CLAUDE.md`.
