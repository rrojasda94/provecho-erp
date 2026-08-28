- **Botón para bloquear la pantalla del PDV a voluntad** (2026-08-28,
  RN-POS-014). El bloqueo por inactividad ya existía, pero son cinco minutos:
  quien se alejaba de la caja no tenía forma de cerrarla al irse y dejaba la
  sesión operable a quien pasara. Es el mismo overlay de ADR-045, con su PIN y
  su "Cambiar de usuario".
- **Recorrer la carta con el dedo cuenta como estar operando** (2026-08-28).
  El bloqueo por inactividad solo miraba `pointerdown` y `keydown`, así que en
  una tablet la pantalla se bloqueaba en la cara de quien la estaba usando.
