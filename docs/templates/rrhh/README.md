# Plantillas de documentos de RRHH

Plantillas rellenables para el módulo de Recursos Humanos, gestionadas
desde el ERP y compartidas por todas las empresas del grupo. Los campos se
completan con datos de la base de datos del ERP o manualmente al emitir.

## Convención de campos

- `{{ entidad.campo }}` — **autocompletado** desde la base de datos del ERP
  (ej. `{{ empresa.razon_social }}`, `{{ trabajador.cargo }}`).
- `[[ COMPLETAR: descripción ]]` — **manual**, se llena al emitir el
  documento (dato que no vive en la base de datos).
- `{{ hoy }}` — fecha de emisión (fecha del sistema).

## Roles → cómo se resuelven a datos

Los roles de un documento (**emisor**, **destinatario**, **representante**,
**aprobador**) **no son tablas**: son papeles que juega una persona. Al
emitir, cada rol se ata a un `trabajador` (personal interno), y sus datos
personales se leen de la entidad **`persona`** (fuente única — RN-GEN-007).
Así, un placeholder como `{{ emisor.nombres }}` significa:
*rol emisor → su `trabajador` → su `persona.nombres`*.

Campos expuestos por cada rol:

| Origen | Campos |
|--------|--------|
| `persona` (vía el trabajador del rol) | `nombres`, `apellidos`, `tipo_documento`, `numero_documento`, `domicilio` |
| `trabajador` | `cargo`, `area`, `fecha_ingreso`, `fecha_cese`, `remuneracion_base`, `saldo_vacaciones` |

Por eso `{{ trabajador.nombres }}` = `persona.nombres` del trabajador, y
`{{ emisor.cargo }}` = `trabajador.cargo` del emisor. Ninguna persona se
escribe dos veces en la base.

## Origen de datos (entidades del ERP)

Ver [data-model.md](../../architecture/data-model.md#8b-recursos-humanos-módulo-rrhh--spec-inicial):
`persona` (datos de la persona), `empresa`, `trabajador`, `contrato_laboral`,
`boleta_pago`, `memorandum`, `amonestacion`, `acta`, `certificado_trabajo`,
`liquidacion_bss`, `solicitud_permiso`, `pacto_permanencia`, `sucursal`.

## Plantillas

| Plantilla | Uso | Base legal (Perú) |
|-----------|-----|-------------------|
| [memorandum.md](memorandum.md) | Comunicación interna formal | Poder de dirección |
| [certificado-trabajo.md](certificado-trabajo.md) | Constancia al cese | Art. 45, D.S. 001-96-TR |
| [carta-amonestacion.md](carta-amonestacion.md) | Sanción disciplinaria escrita | Art. 9, D.S. 003-97-TR (LPCL) |
| [acta.md](acta.md) | Constancia formal de un hecho | — |
| [solicitud-permiso-licencia-vacaciones.md](solicitud-permiso-licencia-vacaciones.md) | Ausencia del trabajador | D.Leg. 713 (vacaciones) |
| [pacto-permanencia-capacitacion.md](pacto-permanencia-capacitacion.md) | Compromiso por capacitación financiada | Código Civil + principios laborales |

### Reclutamiento y contratación

| Plantilla | Uso | Base legal (Perú) |
|-----------|-----|-------------------|
| [convocatoria-puesto.md](convocatoria-puesto.md) | Publicación de búsqueda | Ley 26772 (no discriminación) |
| [ficha-entrevista-evaluacion.md](ficha-entrevista-evaluacion.md) | Evaluación de candidatos | — |
| [carta-oferta-trabajo.md](carta-oferta-trabajo.md) | Oferta escrita antes de la firma | — |
| [ficha-datos-trabajador.md](ficha-datos-trabajador.md) | Datos para contrato y planilla | Ley 29733 (datos personales) |
| [contrato-plazo-indeterminado.md](contrato-plazo-indeterminado.md) | Contrato de puesto permanente | D.S. 003-97-TR; D.S. 013-2013-PRODUCE (microempresa) |
| [contrato-sujeto-a-modalidad.md](contrato-sujeto-a-modalidad.md) | Contrato con causa objetiva y plazo | Arts. 53-83, D.S. 003-97-TR |
| [contrato-tiempo-parcial.md](contrato-tiempo-parcial.md) | Jornada menor a 4 h/día | Art. 4, D.S. 003-97-TR; arts. 11-13, D.S. 001-96-TR |
| [checklist-alta-trabajador.md](checklist-alta-trabajador.md) | Verificación de todo el proceso de ingreso | — |
| [acta-entrega-uniforme.md](acta-entrega-uniforme.md) | Entrega/devolución de uniforme y EPP | RN-RRHH-014 |

## ⚠ Aviso legal

Estas plantillas son una base profesional de RRHH, **no constituyen
asesoría legal**. Antes de su uso deben ser **visadas por un abogado**
(RN-CTR-002 / RN-RRHH-007) y **adaptadas a la normativa vigente** al
momento de emitirse. Las referencias legales pueden cambiar; verificarlas
contra la norma actual (SUNAFIL, MTPE, SUNAT).
