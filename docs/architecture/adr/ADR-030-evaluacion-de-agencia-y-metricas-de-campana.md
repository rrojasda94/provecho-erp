# ADR-030 — Evaluación de agencia y acumulado de campaña

- Estado: aceptado
- Fecha: 2026-08-08

## Contexto

Dos deudas del módulo `marketing` que se cierran juntas porque comparten la
misma pregunta: **¿qué le queda escrito al negocio de lo que hizo Marketing?**

**1. Evaluación de agencia (RN-MKT-006) sin modelo.** La decisión
agencia-vs-interna se documentaba fuera del ERP, en un archivo suelto. Seis
meses después, cuando alguien pregunta por qué se pagó lo que se pagó, no hay
nada que mostrar: ni los criterios, ni las propuestas descartadas, ni quién
firmó.

**2. Eventos sin consumidor.** `marketing.campana_lanzada` y
`marketing.lead_generado` se publicaban y **nadie los escuchaba** (declarado
en el ROADMAP: "se publican pero nadie escucha; candidato natural: BI"). Un
evento sin consumidor no es una extensión futura: es código que corre y no
hace nada, y que nadie sabe si funciona porque ningún test lo mira desde el
otro lado.

## Decisión

### Evaluación de agencia

**1. Dos tablas: `evaluacion_agencia` + `opcion_agencia`.** La evaluación
declara el objetivo, el presupuesto de referencia y los **criterios
ponderados**; cada opción es una propuesta con su costo, plazo y puntaje por
criterio.

**2. Los criterios se congelan al crear la evaluación**, antes de ver las
propuestas, y sus pesos tienen que sumar 100. Cambiar el peso después de
recibir las ofertas es elegir primero y justificar después, que es
exactamente lo que RN-MKT-006 existe para evitar.

**3. La opción interna es obligatoria para cerrar.** No se puede cerrar una
evaluación sin al menos dos propuestas y una de tipo `interna`. Comparar tres
agencias entre sí no contesta la pregunta que la regla hace, que es **si hace
falta una agencia**.

**4. El presupuesto filtra, no descuenta puntos.** La recomendada es la mejor
puntuada **entre las que caben** en el presupuesto. Una propuesta que se pasa
no es "un poco peor": es una que no se puede pagar (RN-GER-003). Si ninguna
cabe, se devuelve igual la mejor puntuada — la decisión sube a Gerencia, y
para decidir necesita ver un candidato.

**5. Evaluar y decidir son permisos distintos.** `marketing.agencia_evaluar`
(rol `marketing`) arma la comparación; `marketing.agencia_decidir` (rol
`supervisor`) la firma. Misma separación que el brief: quien lo redacta no lo
aprueba (RN-MKT-003).

**6. Apartarse de la recomendación exige motivo escrito.** Elegir una opción
que no es la recomendada, o una que excede el presupuesto, se puede — pero no
en silencio. Es el único control real que le queda a Gerencia sobre esta
decisión, y sin él la evaluación sería un trámite.

**7. `opcion_agencia.proveedor_id` va sin FK.** `proveedor` es dominio de
`purchases`; atar los dos módulos por la base sería la misma dependencia que
el código evita. La agencia es un **servicio**: se formaliza por contrato y
la paga Contabilidad, no pasa por `purchases`, que compra el material
(RN-MKT-004).

### Acumulado de campaña

**8. El consumidor de los eventos de marketing es `marketing`.** No BI. La
campaña es de marketing y quien sabe qué significa "convertido" es marketing.
`campana_metrica` acumula: leads generados, leads convertidos, piezas
publicadas, encuestas enviadas/respondidas y suma de puntajes.

**9. Dos eventos nuevos y uno unificado.** Se agregan
`marketing.lead_atribuido`, `marketing.pieza_publicada` y
`marketing.encuesta_respondida`. La atribución **automática** (listener de
`sales.venta_confirmada`) también publica `lead_atribuido` en vez de tocar el
contador directo: atribución manual y automática tienen que sumar por el
mismo camino, o una de las dos se olvida de sumar.

**10. La satisfacción se acredita por la cadena lead → venta → encuesta.** La
encuesta no cuelga de una campaña: cuelga de una venta. El puente es el lead
atribuido. Una encuesta de un cliente que llegó solo no le suma a ninguna
campaña, que es exactamente lo correcto.

**11. El acumulado es derivado y reconstruible.**
`POST /campanas/{id}/metricas/recalculo` lo rehace desde las tablas. Un
acumulado por eventos sin forma de repararlo queda corto para siempre en
cuanto un worker se caiga.

**12. Conversión y puntaje promedio se calculan al leer**, no se guardan.
Guardarlos obligaría a recalcular dos campos cada vez que cambia uno, y a
mantener sincronizado lo que una división resuelve gratis.

## Alternativas descartadas

**Una sola tabla con las propuestas en JSONB.** Menos DDL y hace imposible
preguntar "qué agencias evaluamos el año pasado y cuánto pedían", que es la
consulta por la que la tabla existe.

**Guardar el puntaje ponderado solo al leer.** La fórmula podría cambiar, y
entonces el ranking histórico cambiaría solo: una decisión que en su momento
eligió a la mejor puntuada pasaría a verse arbitraria. Se persiste
`puntaje_total`.

**No guardar acumulado y calcular todo con consultas.** Correcto y más
simple, pero deja los eventos sin consumidor —que es la deuda que se estaba
cerrando— y obliga a cuatro consultas cada vez que alguien abre el tablero de
una campaña.

**Que BI (`core/reportes`) consuma los eventos.** `core` no puede conocer el
dominio de un módulo (`tests/test_arquitectura.py` lo prohíbe), y "leads
convertidos" es una definición de marketing, no de BI. BI lee la tabla.

## Consecuencias

- Dos permisos nuevos en el seeder (`marketing.agencia_evaluar`,
  `marketing.agencia_decidir`) repartidos entre los roles `marketing` y
  `supervisor`.
- `campana_metrica` es cache: si se corrompe, se recalcula. No es fuente de
  verdad de nada y ningún caso de uso decide en base a ella.
- La deuda "`campana.aprobada_por` apunta a `usuario`, no a
  `decision_gerencial`" **sigue abierta**: la evaluación de agencia registra
  quién firmó, no un acta de Gerencia. Se cierra con el slice de Gerencia.
