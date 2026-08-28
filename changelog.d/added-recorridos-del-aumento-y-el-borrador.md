- **Dos recorridos de uso nuevos y una prueba de sesión** (2026-08-28). El
  aumento a una mesa abierta —línea "Sin enviar", "Enviar aumento (N)" y dos
  pastillas en cocina— y el borrador que sobrevive a recargar la página van a
  `uso/`, con captura en cada hito: es el recorrido que hay que mostrarle al
  turno para que reconozca su propio problema arreglado. La renovación de
  sesión va a `e2e/`, que es donde entra por el techo de
  `testing-strategy.md` §1: borra la cookie de acceso —exactamente lo que el
  navegador hace a los quince minutos— y comprueba que la pantalla no caiga a
  `/login` y que el refresh haya rotado.
- **El seeder de e2e siembra una estación de cocina** (2026-08-28). Sin ella,
  cualquier recorrido que quisiera ver la cola tenía que crearla a mano
  primero: quince clics de preparación que no son lo que la prueba viene a
  mirar.
