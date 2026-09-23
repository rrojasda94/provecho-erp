- **El modo oscuro no tenía contraste en el back office** (2026-09-23,
  enmienda a ADR-037). `text-dark`, `text-gray`, `bg-cream` —más de 900 usos—
  colgaban de colores de marca que no cambian con el tema: texto casi negro
  sobre fondo casi negro. Ahora apuntan al rol (texto, texto secundario,
  fondo) y siguen al tema, sin cambiar nada en modo claro. También: tarjetas
  `bg-white` fijas, botones con `text-white` sobre el naranja claro del tema
  oscuro, insignias ámbar/rojo fijas, el texto ámbar de alerta (1.8:1 en
  claro) y dos clases que no existían (`border-borde`, `bg-fondo`). Un test
  nuevo verifica AA (4.5:1) en cada par texto/superficie de los dos temas.
