# Área de Recursos Humanos — Grupo Majambo

Documentación del área de RRHH para personal operativo de restaurantes
(multi-marca, multi-sucursal). El área la ejecuta el **administrador/gerente**
con apoyo del encargado de tienda; no hay puesto dedicado de RRHH.

## Flujo completo de incorporación

```
Necesidad de personal (encargado de tienda)
  → 1. Requisición y perfil de puesto
  → 2. Publicación de convocatoria
  → 3. Filtrado de CVs y preselección
  → 4. Entrevista y evaluación
  → 5. Verificación de referencias y documentos
  → 6. Selección y oferta
  → 7. Elección de modalidad de contrato
  → 8. Firma de contrato y alta (T-Registro, antes del día 1)
  → 9. Apertura de file personal
  → 10. Inducción al grupo / empresa / marca        (día 1)
  → 11. Entrega de uniforme                          (día 1)
  → 12. Inducción al puesto operativo                (semana 1)
  → 13. Evaluación de periodo de prueba              (mes 1-3)
```

Cada paso tiene su SOP en
[docs/diagrams/Procesos/Recursos-Humanos/](../diagrams/Procesos/Recursos-Humanos/):
`Reclutamiento/` (pasos 1-6), `Contratacion/` (7-9), `Induccion/` (10-13).

## El flujo en el ERP: un tablero por convocatoria

Desde 2026-08-01 los 13 pasos se manejan en **un solo tablero** (módulo RRHH →
Convocatorias), una columna por etapa:

```
recibido → preseleccionado → entrevistado → verificado → oferta_enviada
         → contratado → inducido → confirmado          (· descartado)
```

- La **convocatoria** es el expediente de la búsqueda: se crea desde la
  requisición aprobada (paso 1) y no se publica sin perfil de puesto
  (RN-RRHH-013).
- Los postulantes llenan un **Google Form** cuyo enlace va en el aviso; cada
  respuesta entra sola a la columna `recibido` (ver el SOP de publicación de
  convocatoria para el formulario y su conexión).
- El candidato **no es una persona registrada del ERP** mientras es candidato:
  su ficha vive aparte y recién al contratar se crea su `persona` y su
  `trabajador`. Nadie entra a la base de personas por haber postulado.
- Se avanza de a una columna y **descartar exige motivo escrito** — es lo que
  sustenta la decisión si después hay un reclamo.
- La ficha se cierra en `confirmado`, al pasar el periodo de prueba (paso 13),
  no al firmar el contrato.

## Documentos del área

| Documento | Contenido |
|---|---|
| [marco-legal-laboral.md](marco-legal-laboral.md) | Régimen microempresa REMYPE, modalidades de contrato, obligaciones al contratar, plan de salida del régimen |
| [perfiles/](perfiles/) | Perfiles de puestos operativos (funciones, requisitos, competencias) + plantilla para crear nuevos |
| [../templates/rrhh/](../templates/rrhh/README.md) | Plantillas rellenables: contratos, convocatoria, ficha de entrevista, oferta, checklist de alta, acta de uniforme, y documentos de gestión (memorándum, amonestación, etc.) |

## Principios del área

- **Nada verbal**: todo contrato, oferta, entrega y sanción queda por escrito
  y registrado en el ERP (RN-CTR-004, RN-RRHH-007).
- **Nadie trabaja sin alta**: contrato firmado + T-Registro antes del primer
  turno. Sin excepciones — la multa de SUNAFIL por trabajador no registrado
  supera por mucho cualquier apuro operativo.
- **Perfil antes de convocatoria**: no se publica búsqueda sin perfil de puesto
  aprobado; evita contratar "al que caiga".
- **La modalidad de contrato la decide la necesidad real**, no la costumbre
  (ver árbol de decisión en el SOP de elección de modalidad).
- **Capacitación**: la inducción usa el material de
  [docs/capacitacion/](../capacitacion/) (ej. FEFO/FIFO para cocina y almacén).
