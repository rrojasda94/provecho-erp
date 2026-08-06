import { redirect } from "next/navigation";

/** El módulo no tiene portada propia: entra por su primera sección. Existe
 * para que `/gerencia` a secas no sea un 404. */
export default function GerenciaPage() {
  redirect("/gerencia/parametros");
}
