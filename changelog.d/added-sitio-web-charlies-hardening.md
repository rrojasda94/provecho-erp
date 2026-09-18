- **Playwright, SEO y auditoría del sitio de Charlie's Pizzas, PR4**
  (2026-09-18). Suite `storefront/e2e` (carrito → checkout de invitado →
  confirmación) con job propio en CI; construyéndola aparecieron y se
  arreglaron dos bugs reales de hidratación (un `<a>` anidado en la tarjeta
  de favorito, y el carrito leyendo `localStorage` antes de que el cliente
  terminara de hidratar) que no eran visibles probando a mano. `sitemap.ts`,
  metadata Open Graph y JSON-LD (Restaurant, Product) para que el sitio se
  indexe. Auditoría (`audit_log`) en cambios de contenido, fotos,
  direcciones, cuenta y pedido.

- **Aislamiento de credenciales del sitio, probado y no solo declarado.**
  `tests/test_storefront_aislamiento_credenciales.py` fuerza secretos de JWT
  distintos entre el ERP y el sitio (comparten un placeholder por defecto en
  desarrollo, que puede hacer pasar una prueba de aislamiento por la razón
  equivocada) y confirma que ningún token cruza al lado que no le
  corresponde.
