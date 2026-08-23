/**
 * Padrón de clientes visto desde el navegador — solo la carga masiva.
 *
 * La pantalla de clientes corrige de a uno con Server Actions
 * (`ventas/clientes/actions.ts`), y eso se queda como está. La importación va
 * por acá porque una subida `multipart` tiene que salir del navegador y pasar
 * por el proxy, que es el camino que conserva los bytes y el `boundary`
 * (ADR-048). Meterla en una Server Action obligaría a reenviar el archivo dos
 * veces por un camino que nadie probó.
 */

import { pedir, subir } from "@/lib/cliente-api";

export const RUTA_PLANTILLA_CLIENTES =
  "/api/proxy/api/v1/sales/clientes/plantilla";

/** El mismo libro que la plantilla, con el padrón adentro (ADR-052). */
export const RUTA_EXPORTAR_CLIENTES = "/api/proxy/api/v1/sales/clientes/exportar";

export type ClienteRevisado = {
  fila: number;
  /** El id que trajo la columna `ID`, o el que resolvió el documento. */
  id: string | null;
  accion: "crear" | "actualizar" | "omitir";
  /** Se deriva del documento, no se declara (RN-PTS-002). */
  tipo: string;
  nombre: string;
  tipo_documento: string;
  documento: string;
  telefono: string;
  email: string;
  contacto: string;
  fecha_nacimiento: string | null;
  cambios: string[];
  problemas: string[];
};

export type RevisionClientes = {
  clientes: ClienteRevisado[];
  listas: number;
  a_actualizar: number;
  con_problema: number;
};

export type ResultadoImportacionClientes = {
  creadas: { id: string; nombre: string }[];
  actualizadas: { id: string; nombre: string }[];
  omitidas: { nombre: string; motivo: string }[];
};

export const clientesApi = {
  validarImportacion: (archivo: File) =>
    subir<RevisionClientes>("/sales/clientes/importar/validar", archivo),

  /** Manda **solo lo que el contrato declara**: la revisión trae además
   * `fila`, `tipo`, `cambios` y `problemas`, que son para la pantalla. */
  importarClientes: (clientes: ClienteRevisado[]) =>
    pedir<ResultadoImportacionClientes>("/sales/clientes/importar", {
      metodo: "POST",
      cuerpo: {
        clientes: clientes.map((c) => ({
          id: c.id,
          accion: c.accion,
          nombre: c.nombre,
          tipo_documento: c.tipo_documento,
          documento: c.documento,
          telefono: c.telefono,
          email: c.email,
          contacto: c.contacto,
          fecha_nacimiento: c.fecha_nacimiento,
        })),
      },
    }),
};
