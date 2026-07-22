# SOP — Control de calidad y manejo de no conformidad

**Área:** Producción · **Grupo:** Calidad e Inocuidad

## Objetivo
Que ningún lote no conforme llegue al almacén central ni a un cliente, y
que toda no conformidad quede registrada y resuelta — corregida o
desechada con evidencia, nunca sin rastro.

## Frecuencia
Cada orden de producción, antes de habilitar su despacho al almacén
central (RN-PRD-013).

## Responsable
Jefe de cocina (producción) evalúa y decide; cocinero de producción
reporta el hallazgo apenas lo detecta.

## Materiales y equipo
- ERP: módulo de producción (control de calidad de la orden), reporte de
  escalamiento
- Cámaras de videovigilancia del establecimiento (destrucción solo en
  zona cubierta, nunca fuera del local)
- Plantilla: [ficha-no-conformidad](../../../../templates/produccion/ficha-no-conformidad.md)

## Pasos
1. Al finalizar la orden de producción, evaluar el lote contra el
   criterio de calidad de la receta (sabor, textura, temperatura,
   envasado/etiquetado según corresponda).
2. Si **conforme** → registrar `control_calidad_resultado = conforme` en
   el ERP, habilitar despacho al almacén central.
3. Si **no conforme** → jefe de cocina evalúa si es corregible:
   - **Corregible** (reproceso, ej. ajuste dentro de receta flexible,
     RN-PRD-010) → reprocesar, registrar
     `control_calidad_resultado = no_conforme_reprocesado`.
   - **No corregible** → desechar como merma, registrar
     `control_calidad_resultado = no_conforme_desechado`.
4. En cualquiera de los dos casos "no conforme", generar un reporte de
   escalamiento (origen `produccion`, motivo `no_conformidad_calidad`,
   RN-PRD-014): describir qué se encontró y qué acción se tomó.
5. Si el resultado fue desecho: destruir el lote dentro del
   establecimiento, en zona cubierta por cámaras (nunca fuera del local)
   y dentro del horario laboral, y desecharlo finalmente a la basura. El
   video de la destrucción se adjunta como evidencia al reporte de
   escalamiento (RN-PRD-015). Sin evidencia, el reporte no se cierra.
6. Reincidencia del mismo motivo de no conformidad (ej. 2+ veces en el
   mismo periodo) → escalar el reporte a Comercial/Gerencia para revisar
   receta o proceso, no solo el lote puntual.

## Excepciones
- No conformidad detectada ya en tránsito hacia sucursal (raro, dado que
  el control es previo al despacho) → tratar como devolución, no como
  este SOP; coordinar con Almacén.
- Duda razonable entre reproceso y desecho → por defecto, desechar; el
  jefe de cocina no arriesga calidad por ahorrar el insumo.

## Problemas frecuentes
| Síntoma | Causa | Corrección |
|---|---|---|
| Lote desechado sin evidencia registrada | Se prioriza rapidez sobre el registro | Paso 5 obligatorio antes de cerrar el reporte |
| No conformidad se resuelve verbalmente, sin reporte | Se ve como "cosa menor" | Paso 4 obligatorio para cualquier resultado no conforme, sin excepción |
| Mismo defecto se repite sin que nadie revise la receta | Cada hallazgo se trata aislado | Paso 6: reincidencia dispara revisión de receta/proceso, no solo del lote |

## Checklist de verificación
- [ ] Lote evaluado contra criterio de calidad antes de despacho
- [ ] Resultado registrado en el ERP (`conforme` / `no_conforme_*`)
- [ ] Reporte de escalamiento generado si no conforme
- [ ] Destrucción realizada dentro del establecimiento, en zona con
  cámaras, en horario laboral, con desecho final a la basura — video
  adjunto si el lote se desechó
- [ ] Reincidencia revisada contra reportes anteriores

## Evidencia y supervisión
Reporte de escalamiento con evidencia archivado en el ERP. Gerencia y
Comercial revisan reincidencias por receta/proceso periódicamente
[[ COMPLETAR ]].
