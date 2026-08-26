- **La cocina ahora sabe cuánto lleva esperando cada pedido** (2026-08-26). El
  KDS no tenía **ninguna** noción de tiempo: los colores de la tarjeta eran el
  estado (`en_preparacion` ámbar, `listo` verde), que dice en qué anda el
  pedido pero no si lleva cuatro minutos o cuarenta. Un pedido olvidado se veía
  exactamente igual que uno recién tomado. Cada tarjeta muestra ahora su reloj
  y cambia de color al pasar dos umbrales. Un pedido ya `listo` se queda verde
  por más que espere: ese no espera por la cocina, espera por quien despacha.
- **Los umbrales y los colores los fija Gerencia**, en
  **Gerencia → Tiempos del KDS**, con el mismo mecanismo de aprobación que la
  tarifa del delivery (ADR-014 Addendum): nada llega a la cocina hasta que se
  aprueba. Se configura y no se fija en el código porque ocho minutos son una
  eternidad para una barra de bebidas y nada para un horno de pizza a leña — el
  número correcto lo sabe quien mira la cocina. Los colores se eligen con el
  `<input type="color">` del navegador, y la pantalla de aprobación muestra la
  muestra de color: aprobar un `#f87171` sin verlo es aprobar un código
  hexadecimal.
- **El reloj lo corre el navegador.** El backend suma `creado_en` a la cola y
  expone los umbrales en `GET /kds/configuracion`; un cronómetro servidor
  obligaría a recalcular y reenviar la cola entera cada segundo por algo que la
  pantalla ya sabe. El reloj avanza con el refresco que ya existía, sin
  temporizador propio.
- **Un valor mal aprobado no deja la cocina sin pantalla.** Un color que no es
  un color, un umbral de cero —que pintaría todo de rojo desde el primer
  segundo y apagaría el semáforo sin decirlo— o un rojo anterior al ámbar caen
  a los valores de fábrica. En el último caso caen **los dos**: corregir uno
  contra el otro dejaría una combinación que nadie aprobó.
