- **El reparto propio se especificó como módulo aparte** (ADR-098): rutas
  con varias paradas optimizadas contra Google Routes (fallback
  heurístico), GPS del repartidor, enlace público de seguimiento con mapa
  en vivo, aviso automático por WhatsApp y entrega fallida con motivo y
  evidencia — todo separado de `sales`, que solo se entera por evento
  (`delivery.entrega_registrada`) y nunca se importa desde `delivery`. Este
  cambio es solo documentación y contratos (README, `data-model.md` §6b,
  `events.md`, RN-DLV-001 a 008, máquinas de estado); el código llega en
  los slices siguientes.
