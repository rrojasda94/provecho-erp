- **El efectivo admite sobrepago y el vuelto se guarda** (2026-08-28). Hasta
  ahora la suma de los pagos tenía que **igualar** el total, así que el cajero
  no podía aceptar un billete de 50 por una cuenta de 33.30: para cobrar tenía
  que teclear el saldo de memoria, al centavo, con el cliente esperando. El
  vuelto se mostraba, pero solo en el navegador — se calculaba en el diálogo y
  moría ahí, y el arqueo no tenía forma de explicar por qué el cajón tenía
  menos billetes que la suma de los cobros. Ahora un monto mayor al saldo se
  acepta en los medios que pueden devolver la diferencia y queda en
  `pago.vuelto`. `pago.monto` sigue siendo lo que entra a la cuenta y nunca
  más que el saldo: meter ahí lo entregado pondría en los libros plata que
  salió del cajón esa misma noche, y obligaría a cinco consumidores distintos
  —cierre de caja, contabilidad, reportes, el replay del hub— a saber restar.
  En tarjeta y billetera el sobrepago se sigue rechazando, ahora diciendo por
  qué: ahí no hay cajón, y la única forma de devolver es una nota de crédito
  al día siguiente. Enmienda RN-COM-016, ADR-077.
