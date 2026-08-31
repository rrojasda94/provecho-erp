- **Elegir «RUC» al dar de alta una persona devolvía 500 — y envenenaba la
  lista** (2026-08-30). El vocabulario de `tipo_documento` estaba escrito en
  cuatro sitios que no coincidían: el `Enum` del modelo conocía
  `dni`/`ce`/`pasaporte`, el formulario de Personas ofrecía además `ruc` y el
  tablero de Contratación mandaba `carne_extranjeria`. Nadie validaba en el
  medio. Y lo peor no era el rechazo: como `Enum(native_enum=False)` no emite
  ningún CHECK (`create_constraint` vale `False` desde SQLAlchemy 1.4), el
  INSERT **entraba** y lo que reventaba era la **lectura** — una sola fila con
  `ruc` tumbaba `GET /personas` para todos, hasta corregirla a mano.
  Ahora `ruc` es un tipo legítimo de persona (una persona natural con negocio
  lo tiene, y su comprobante ya sale con el código 6 del catálogo 06 de SUNAT
  en vez de «sin documento»), `carne_extranjeria` se normaliza a `ce`, el
  número se valida contra su tipo (DNI 8 dígitos, RUC 11, CE y pasaporte
  alfanuméricos) y el vocabulario vive una sola vez en `src/shared/documento.py`
  y `frontend/lib/documento.ts`. La migración `c9f4a2e70b18` sanea lo que haya
  quedado guardado y **crea el CHECK que nunca existió**: el mismo error vuelve
  a ser un alta rechazada y no una fila ilegible para siempre.
- **La ficha de una persona sin documento rompía la serialización**: `PersonaOut`
  declaraba `tipo_documento` y `numero_documento` obligatorios contra columnas
  nulas desde `e1c4a9d6b038` (ADR-018), y toda persona creada desde el PDV nace
  sin documento. Costo aceptado: el barrido del resto del contrato
  (`openapi.json`, ADR-010) queda para su propia rama.
