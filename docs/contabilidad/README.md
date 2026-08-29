# Área de Contabilidad — Grupo Majambo

Registra, controla y mueve el dinero del grupo. Hoy concentra **tres
funciones** que en empresas más grandes viven separadas; a la escala actual
las ejecuta la misma área (contador/tesorero), con **Gerencia como supervisor
directo** (control compensatorio, ver [política](politica-contabilidad.md)).

## Las tres funciones (los tres sombreros)

| Función | Qué hace | Pregunta que responde |
|---|---|---|
| **Tesorería** | Mueve el dinero: caja, bancos, custodia de efectivo, pagos a proveedor, reposición de caja chica, depósitos. | ¿Dónde está el efectivo y a quién se le paga? |
| **Finanzas** | Planea el dinero: flujo de caja proyectado, liquidez, presupuesto (con Gerencia), márgenes objetivo (con Comercial). | ¿Alcanza el dinero y para qué? |
| **Contabilidad (registro)** | Registra el dinero: asientos, comprobantes, libros, tributos, activos fijos, cierre de periodo. | ¿Qué pasó y cómo se declara? |

> **Por qué juntas hoy:** el grupo es una microempresa; separar tesorería de
> registro exigiría más personal del que hay. Se acepta el riesgo de forma
> explícita y se compensa con supervisión de Gerencia. Cuando el volumen lo
> justifique, la ruta de separación está descrita en la
> [política](politica-contabilidad.md#segregación-de-funciones-y-supervisión).

## El dinero entra y sale por aquí

```
INGRESOS                                      EGRESOS
Recaudación de caja (cobro POS)               Pago a proveedor (tras comprobante
  → cadena de custodia (RN-MDP-002):            conforme de Compras, RN-CMP-014)
    cajero → supervisor → Contabilidad        Reposición de caja chica (RN-CMP-013)
  → depósito bancario                         Planilla y aportes (con RRHH)
Cobros a crédito empresarial                  Tributos y detracciones (SUNAT)
  (regularizados por Contabilidad)            Servicios, mantenimiento, activos
        ↓                                            ↓
        └──────────→  CONCILIACIÓN BANCARIA  ←───────┘
                      (ERP vs. banco, periódica)
                              ↓
                      CIERRE DE PERIODO → libros y declaración (contador)
```

## Control y auditoría interna

Además de mover, planear y registrar, Contabilidad ejerce **control interno**:
audita a las áreas operativas que están *aguas arriba* de ella. Puede hacerlo
porque es independiente de ellas — no compra, no almacena, no cobra en el POS.

**Regla que lo rige (RN-CTB-009):** una auditoría/arqueo la ejecuta **quien no
custodia** ese fondo o dato. De ahí salen dos niveles:

| Auditor | Audita a | Qué revisa |
|---|---|---|
| **Contabilidad** (control interno) | **Compras** | Arqueo inopinado de la caja chica de compras; match factura ↔ OC ↔ recepción (3-way, PROC-CTB-013) |
| | **Almacén** | Conteo inopinado o disparado por alerta `inventory.ajuste_fuera_margen` (RN-INV-015), con el encargado de almacén como testigo (PROC-CTB-012) |
| | **Sucursales** | Arqueo inopinado de la caja del POS |
| **Gerencia** | **Contabilidad** | Su propia tesorería: depósitos, pagos ejecutados, conciliación bancaria (visado), custodia de efectivo propia |

> **Contabilidad no se audita a sí misma** (RN-CTB-009). La conciliación
> semanal de cuentas y depósitos la *ejecuta* Contabilidad (operativo), pero el
> *visado* de esa conciliación lo da Gerencia (auditoría) — RN-CTB-006. Es el
> nivel superior el que cierra el hueco de segregación del inferior.

Los arqueos de caja de sucursal y de caja chica de compras **reusan el SOP de
[arqueo sorpresa](../diagrams/Procesos/Contabilidad/Control/arqueo-sorpresa.md)
(PROC-CTB-005)** — es genérico; solo cambian el custodio y el ejecutor según la
regla de arriba.

## Procesos del área (SOPs)

Ubicación: [docs/diagrams/Procesos/Contabilidad/](../diagrams/Procesos/Contabilidad/).

| SOP | Grupo | Estado | Cubre |
|---|---|---|---|
| Apertura de caja (PROC-CTB-002) | `Caja/` | ✅ Vigente | Inicio de turno, fondo inicial |
| Cierre de caja (PROC-CTB-001) | `Caja/` | ✅ Vigente | Cierre de turno, cuadre, relevo de custodia |
| Pago a proveedor (PROC-CTB-003) | `Tesoreria/` | ✅ Vigente | Ejecuta el pago tras comprobante conforme; umbral de aprobación de Gerencia |
| Conciliación bancaria (PROC-CTB-004) | `Tesoreria/` | ✅ Vigente | Cuadra movimientos ERP vs. extracto bancario |
| Arqueo sorpresa (PROC-CTB-005) | `Control/` | ✅ Vigente | Conteo no anunciado de caja/fondos; ejecuta quien no custodia (RN-CTB-009) |
| Auditoría inopinada de almacén (PROC-CTB-012) | `Auditoria/` | ⬜ Propuesto | Conteo sorpresa o por alerta (RN-INV-015), con encargado como testigo |
| Conciliación de facturas y comprobantes (PROC-CTB-013) | `Auditoria/` | ⬜ Propuesto | 3-way match factura ↔ OC ↔ recepción; control sobre Compras |
| Reposición de caja chica (PROC-CTB-006) | `Tesoreria/` | ⬜ Propuesto | Concilia la rendición semanal y repone el fondo |
| Flujo de caja semanal (PROC-CTB-007) | `Finanzas/` | ⬜ Propuesto | Proyección de ingresos/egresos, alerta de liquidez |
| Cierre mensual / periodo contable (PROC-CTB-008) | `Cierre/` | ⬜ Propuesto | Bloqueo de periodo, entrega al contador (RN-CTB-002) |
| Depósito de recaudación (PROC-CTB-009) | `Tesoreria/` | ⬜ Propuesto | Depósito bancario del efectivo custodiado |
| Alta y control de activo fijo (PROC-CTB-010) | `Activos/` | ⬜ Propuesto | Registro, depreciación y baja de activos (ACT) |
| Coordinación con contador externo (PROC-CTB-011) | `Tributos/` | ⬜ Propuesto | Entrega de información, plazos SUNAT, detracciones |

Los ⬜ propuestos se redactan uno a uno; el orden y alcance se afinan con el
usuario (mismo criterio que las demás áreas: primero lo que ya opera).

## Documentos del área

| Documento | Contenido |
|---|---|
| [politica-contabilidad.md](politica-contabilidad.md) | Principios, segregación de funciones/supervisión de Gerencia, riesgo aceptado y ruta de upgrade |
| [marco-legal-contabilidad.md](marco-legal-contabilidad.md) | Comprobantes, IGV/Régimen Amazonía, detracciones, libros electrónicos, plazos SUNAT, contador externo, activo fijo/depreciación |
| [perfiles/](perfiles/) | Perfil del contador/tesorero |
| [../templates/contabilidad/](../templates/contabilidad/) | Conciliación bancaria, arqueo de caja, flujo de caja semanal, orden de pago |

## Principios del área

- **Quien mueve el dinero no lo aprueba solo** — todo egreso sobre el umbral
  lo aprueba Gerencia antes de ejecutarse (RN-CTB-005). Es el control que
  reemplaza la separación tesorería/registro que hoy no existe.
- **Sin comprobante no hay pago ni registro** — coherente con Compras
  (RN-CMP-005/006). El pago a proveedor solo se ejecuta con comprobante
  conforme entregado por Compras (RN-CMP-014).
- **Todo cuadra o se explica** — arqueos, conciliaciones y cierres dejan la
  diferencia documentada y atribuida; nada se "ajusta" sin rastro (RN-CTB-001).
- **El efectivo tiene dueño en cada momento** — la cadena de custodia
  (RN-MDP-002) no se rompe: cada relevo se autentica con usuario + PIN.
- **La contabilidad refleja, no inventa** — registra los eventos operativos
  que ya ocurrieron (RN-CTB-003); no crea la operación, la documenta.
- **El plan de cuentas es el PCGE, no uno propio** — el Plan Contable General
  Empresarial es obligatorio en el Perú y es con el que trabaja el contador
  externo. Nadie inventa el número de una cuenta que ya existe; el ERP lo
  trae cargado (ADR-080). Ver [marco legal](marco-legal-contabilidad.md).
- **Periodo cerrado es inmutable** — corrección por asiento inverso, nunca
  editando lo cerrado (RN-CTB-002).
- **Gerencia supervisa, no opera** — aprueba, revisa y audita; no lleva la
  caja ni concilia. Separar la supervisión de la ejecución es el punto.

## Relación con otras áreas

- **Compras** entrega el comprobante conforme; Contabilidad ejecuta el pago
  (RN-CMP-014) y repone la caja chica de compras (RN-CMP-013).
- **Comercial** define el margen de contribución mínimo **con** Contabilidad
  (RN-CML-001); Contabilidad regulariza los cobros a crédito empresarial.
- **RRHH** procesa la planilla; Contabilidad ejecuta el pago de remuneraciones
  y aportes.
- **Gerencia** aprueba el presupuesto anual (PROC-GER-001) con insumos de
  Finanzas, y supervisa toda el área (arqueos, aprobaciones, conciliaciones).
- **Almacén/Logística** resguarda la Guía de Remisión que Contabilidad
  archiva; los ajustes fuera de margen (RN-INV-015) llegan como alerta.
