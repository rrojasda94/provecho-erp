- **Agregar o quitar productos de un consumo de personal se firma cada vez**
  (2026-08-30). La firma del alta autorizaba *ese* pedido, no los aumentos que
  vinieran después, y con la orden ya creada cualquiera podía seguir sumando
  platos gratis. Ahora `POST /sales/ventas/{id}/items` exige el token de
  `POST /auth/autorizar` con `sales.registrar_consumo_personal` cuando la
  orden es un consumo, y `anular-lineas` pide firma **aunque la línea esté
  dentro de la ventana de corrección**: esa ventana existe para que el cajero
  arregle su propio tecleo, no para deshacer lo que un encargado firmó.
  **Las ventas normales no cambian**: agregar sigue sin pedirle firma a nadie
  (RN-COM-029) y quitar sigue exigiéndola solo pasados los 5 minutos.
