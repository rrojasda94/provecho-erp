# Nomenclatura de procesos

Estándar para nombrar, versionar y rastrear procesos de negocio (Compras,
Venta, Producción...) a través de `workflows.md`, `use-cases.md`, diagramas
BPMN/Mermaid, eventos y `CHANGELOG.md`. Se aplica desde 2026-07-15; procesos
existentes se migran al tocarlos (ver tabla al final).

## Código

```
PROC-<ÁREA>-<NNN>
```

- **ÁREA**: sigla de 3 letras de un área real de la empresa (no un módulo del
  ERP ni un proceso interno — confirmado por el usuario 2026-07-15). Tabla
  de siglas abajo.
- **NNN**: correlativo de 3 dígitos, único dentro del área, empieza en 001.
  Nunca se reutiliza ni se renumera, aunque el proceso se deprecie.

| Sigla | Área | Sigla | Área |
|-------|------|-------|------|
| RRH | RRHH | GER | Gerencia |
| INV | Logística y Almacén | FIN | Finanzas |
| PRD | Producción | LEG | Legal |
| CTB | Contabilidad | IDI | I+D+i |
| CMP | Compras | MRC | Manejo de marca |
| COM | Comercial | SIS | Sistemas / TI |
| MKT | Marketing | OPE | Operaciones |

`OPE` (Operaciones) agregada 2026-07-16: dueña de procesos operativos de
sucursal que cruzan varias areas (seguridad fisica, limpieza, inocuidad,
recepcion de mercaderia, RRHH de apertura) sin encajar en una sola area de
negocio existente. Tambien evalua y mejora continuamente los procesos del
grupo (mejora continua).

Nueva área sin sigla en la tabla: se propone una sigla de 3 letras sin
choque, se agrega a esta tabla en el mismo cambio.

Nota: `INV` ya se usaba en `RN-INV-001..020` para todo lo que hoy es el
área Logística y Almacén (inventario, solicitudes, picking,
transferencias) — se adopta `INV` como sigla del área en vez de introducir
`LOG`. El proceso Venta, dueño el área Comercial, usa la sigla del área:
`CU-COM-nnn`, `RN-COM-nnn`, `PROC-COM-001` (renombrado desde `VNT` el
2026-07-15 en las ~40 referencias de
[use-cases.md](use-cases.md), [business-rules.md](business-rules.md),
[workflows.md](workflows.md), eventos, máquina de estados y BPMN).

## Procesos/funciones que NO son área

Estos códigos aparecían antes en la tabla de áreas; son procesos o
funciones de plataforma del ERP, cada uno con un área dueña (a confirmar
donde diga "supuesto"):

| Código previo | Qué es | Área dueña |
|---|---|---|
| CAJ (Caja) | Proceso de cobro/manejo de efectivo | Contabilidad (supuesto) |
| CRM | Proceso de fidelización/gestión de clientes | Comercial (supuesto, con insumos de Marketing) |
| TES (Tesorería) | Proceso de flujo de caja y pagos | Finanzas (supuesto) |
| ACT (Activos) | Proceso de control de activos no corrientes | Contabilidad (supuesto) |
| PRY (Proyectos) | Función transversal de seguimiento de proyectos | Gerencia (supuesto) |
| USR, REP, SUP, CFG | Usuarios/accesos, BI/reportes, supervisión/auditoría, settings | Funciones del ERP en sí — no tienen área de negocio dueña; si se necesita rastrearlas, usar `SIS` (Sistemas/TI) |

## Versión

```
v<MAYOR>.<MENOR>
```

SemVer sin PATCH (un documento de proceso no publica parches automáticos;
si hace falta corregir una errata de redacción sin cambio de flujo, se
puede usar `v<MAYOR>.<MENOR>.<PATCH>` puntualmente).

- **MAYOR**: cambia el resultado, alcance o actores del proceso; agrega o
  quita pasos que afectan a otros procesos; rompe un contrato de evento
  (`events.md`) que otros módulos consumen. Requiere revisar módulos
  consumidores y, si toca arquitectura, un ADR.
- **MENOR**: aclara, detalla, agrega un canal/variante o mejora un paso sin
  romper el flujo ni los contratos existentes.
- **PATCH** (opcional): solo redacción/erratas, cero cambio semántico.

Un proceso nuevo arranca en `v1.0`. Mientras está en discusión y sin
decisión firme del usuario, se marca `v0.x` y estado `Borrador`.

## Estado

`Borrador` (en discusión, puede cambiar) · `Vigente` (decisión tomada,
implementable) · `Deprecado` (ya no aplica; referenciar el proceso
sucesor si existe).

## Relación con Casos de Uso

Un proceso (`PROC-<área>-nnn`) se descompone en uno o más Casos de Uso
(`CU-<área>-nnn`) por actor/canal — ver formato en
[use-cases.md](use-cases.md). El CU no tiene versión propia: hereda la del
PROC que documenta. Si el PROC sube de versión y el CU cambia con él, el CU
referencia la nueva versión en su encabezado (`(implementa PROC-COM-001
v1.1)`).

## Dónde vive cada pieza

| Contenido | Ubicación |
|---|---|
| Narrativa + diagrama Mermaid del proceso | Sección propia en [workflows.md](workflows.md), encabezada `## <Nombre> — PROC-<área>-nnn (v<mayor>.<menor>, <estado>)` |
| Casos de uso del proceso | [use-cases.md](use-cases.md), agrupados bajo el mismo nombre de proceso |
| Diagrama BPMN (herramienta externa) | `docs/diagrams/Procesos/<Área en texto>/PROC-<ÁREA>-<NNN>-v<MAYOR>.<MENOR>.bpmn` |
| Eventos que emite/consume | [architecture/events.md](../architecture/events.md), cada evento anota qué PROC lo emite/consume |
| Historial de cambios de versión | `CHANGELOG.md`, sección `Changed`: `PROC-COM-001 v1.0 → v1.1: <resumen>.` |

## Registro maestro

| Código | Nombre | Versión | Estado | Fuente |
|---|---|---|---|---|
| PROC-CMP-001 | Compras | v1.0 | Vigente | [workflows.md](workflows.md#compras) |
| PROC-PRD-001 | Producción | v0.1 | Borrador | [workflows.md](workflows.md#producción-si-existe) |
| PROC-INV-001 | Abastecimiento de locales | v0.2 | Borrador | [workflows.md](workflows.md#abastecimiento-de-locales); v0.2 detalla el conteo de fin de jornada en sucursal (balanzas, QR, ventana de refrigeración, alerta por margen de error RN-INV-015, cálculo de sugerido RN-INV-013); picking/packing/transporte en almacén central sigue sin este nivel de detalle |
| PROC-COM-001 | Venta | v1.0 | Vigente | [workflows.md](workflows.md#venta), decisión de alcance 2026-07-14 |
| PROC-COM-002 | Cobro y Emisión de Comprobante de Pago | v1.0 | Vigente | [workflows.md](workflows.md#cobro-y-emisión-de-comprobante-de-pago), detalle del paso "cobro" de PROC-COM-001 (RN-COM-005), decisión de área 2026-07-15 |
| PROC-CTB-001 | Cierre de caja | v1.1 | Vigente | [workflows.md](workflows.md#cierre-de-caja); área dueña Contabilidad, ver tabla "Procesos/funciones que NO son área" (CAJ); v1.1 agrega la bifurcación de custodia local vs. traslado a oficinas (RN-MDP-006) |
| PROC-CTB-002 | Apertura de caja | v1.0 | Vigente | [workflows.md](workflows.md#apertura-de-caja); área dueña Contabilidad, ver tabla "Procesos/funciones que NO son área" (CAJ); decisión de alcance 2026-07-16 |
| PROC-OPE-001 | Apertura de sucursal | v1.0 | Vigente | [workflows.md](workflows.md#apertura-de-sucursal); área dueña Operaciones (nueva, ver tabla de áreas); referencia a PROC-CTB-002 (apertura de caja) y a los pasos 6-9 de PROC-INV-001 (recepción del pedido de almacén central); decisión de alcance 2026-07-16 |

Al crear o versionar un proceso: actualizar esta tabla en el mismo cambio.
