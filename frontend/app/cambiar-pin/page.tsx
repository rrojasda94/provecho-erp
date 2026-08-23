import { obtenerSesion } from "@/lib/sesion";

import { CambiarPinCliente } from "./cambiar-pin-cliente";

/**
 * La única salida de un PIN reseteado.
 *
 * Vive **fuera** de `(app)`, como el login: el layout del shell manda acá a
 * toda cuenta con `debe_cambiar_pin`, y si esta pantalla estuviera adentro se
 * redirigiría a sí misma para siempre. Tampoco tendría qué mostrar en la
 * barra: desde acá no se puede ir a ningún lado.
 *
 * Quien llega **tiene** sesión; lo que no tiene es un PIN suyo. El servidor le
 * responde 403 a todo lo demás (`api.deps.RUTAS_CON_PIN_TEMPORAL`), así que
 * esta pantalla no depende de que nadie la respete — es la que sí funciona.
 *
 * También sirve para cambiar el PIN por gusto: no hay motivo para esconder
 * detrás de un reseteo algo que cualquiera debería poder hacer cuando quiera.
 */
export default async function CambiarPinPage() {
  const { usuario } = await obtenerSesion();
  return <CambiarPinCliente username={usuario.username} />;
}
