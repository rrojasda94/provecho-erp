- **"Olvidé mi contraseña" en el sitio, y restablecer la clave desde atención al
  cliente** (2026-09-19). Quien olvida su clave pide un enlace con su email
  (vale 30 minutos y una sola vez; la respuesta es la misma exista o no la
  cuenta) y elige una nueva; al cambiarla se cierran sus otras sesiones. Quien
  no tiene un correo al que llegue llama al local, y desde el ERP (**Sitio web →
  Clientes**) se le restablece la clave: sale una **clave temporal que se ve una
  sola vez**, y el cliente tiene que cambiarla al ingresar. También se puede
  cambiar la clave estando adentro. Además: el botón de Google no aparecía en
  staging porque el Client ID nunca llegaba al contenedor del sitio, y sobraba un
  separador "o" cuando el botón no se dibujaba. RN-WEB-018/019, ADR-104
  enmendado, migración `cec53f7b2f6e`. Costo aceptado: el correo necesita
  `SMTP_*` y `STOREFRONT_SITIO_URL` en el servidor (checklist en `staging.md`);
  sin verificación de email al registrarse todavía.
