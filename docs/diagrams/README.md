# Diagramas y procesos

Qué vive aquí y con qué convención:

## Diagramas transversales (Mermaid)

**Mermaid dentro de Markdown** — versionable, diffeable, se renderiza en
GitHub y los agentes de IA pueden editarlo.

- Mapa de módulos y eventos: [modules.md](modules.md)
- ERD: inline en [../architecture/data-model.md](../architecture/data-model.md)
- Flujos operativos: inline en [../domain/workflows.md](../domain/workflows.md)
- Máquinas de estado: inline en [../domain/state-machines.md](../domain/state-machines.md)

## Procesos por área — `Procesos/`

Taxonomía: `Procesos/<Área>/<Grupo>/...`. Áreas actuales: Operaciones,
Comercial, Contabilidad, Compras, Recursos-Humanos, Logistica-Almacen
(carpeta física; el área de negocio se llama "Almacén y Logística").
La venta vive en `Comercial/` — no existe área "Ventas"
(ver [process-nomenclature.md](../domain/process-nomenclature.md)).

Dos tipos de archivo:

1. **SOPs** (`.md`) — procedimientos operativos estándar redactados con la
   plantilla de la skill `sop-creator` (objetivo, frecuencia, responsable,
   materiales, pasos, excepciones, problemas frecuentes, checklist,
   evidencia). Enfoque actual: **primero SOP, luego BPMN** — así se hacen
   mejores conexiones entre procesos antes de diagramar.
2. **BPMN** — diagramas de procesos formales, nombrados
   `PROC-<ÁREA>-<NNN>-v<MAYOR>.<MENOR>.bpmn` (formato de intercambio
   BPMN 2.0, importable en Bizagi). Un `.bpm` con el mismo nombre es el
   archivo de proyecto de Bizagi asociado.

**Versiones antiguas se conservan** (ej. `PROC-CTB-001-v1.0.bpmn` junto a
`v1.1`): sirven para analizar la evolución del proceso y hallar mejoras.
La versión vigente es la que indica el
[registro maestro](../domain/process-nomenclature.md#registro-maestro).
