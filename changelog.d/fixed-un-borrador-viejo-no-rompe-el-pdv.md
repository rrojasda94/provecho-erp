- **Un borrador guardado antes de que el PDV ganara un campo dejaba su campo
  sin control** (2026-08-28, ADR-074). El contenido del borrador es JSONB
  opaco a propósito —para que el formato pueda crecer sin migrar nada—, así
  que un ticket viejo vuelve sin las claves nuevas: React leía `undefined` y
  convertía el input controlado en uno sin control, que deja de responder sin
  decir por qué. Los recuperados se completan contra un borrador nuevo antes
  de pintarse.
