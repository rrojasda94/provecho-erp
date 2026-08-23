"use client";

import { useState } from "react";

import { DialogoImportar } from "@/components/planilla/dialogo-importar";
import {
  clientesApi,
  type ClienteRevisado,
  type RevisionClientes,
  RUTA_EXPORTAR_CLIENTES,
  RUTA_PLANTILLA_CLIENTES,
} from "@/lib/clientes";

/**
 * Carga masiva del padrón de clientes (RN-PTS-007, ADR-052).
 *
 * La identidad de una fila es el `ID` o, si va vacío, el número de documento.
 * El tipo no se declara: lo decide el documento — 11 dígitos es un RUC y hace
 * al cliente jurídico (RN-PTS-002).
 *
 * De un cliente **natural** que ya existe solo se completa el documento. Su
 * nombre, teléfono y dirección viven en su ficha de persona (RN-GEN-007) y no
 * se corrigen desde acá: la revisión lo dice fila por fila en vez de aplicar
 * la mitad del cambio en silencio.
 *
 * Esta carga **no consulta a SUNAT ni a RENIEC**: trescientas filas serían
 * trescientas llamadas externas contra una cuota. El nombre del archivo manda.
 */

type Props = { onImportados: () => void };

export function ImportarClientes({ onImportados }: Props) {
  const [revision, setRevision] = useState<RevisionClientes | null>(null);
  const [clientes, setClientes] = useState<ClienteRevisado[]>([]);

  function abrir() {
    setRevision(null);
    setClientes([]);
  }

  async function revisar(archivo: File) {
    const datos = await clientesApi.validarImportacion(archivo);
    setRevision(datos);
    setClientes(datos.clientes);
  }

  const importables = clientes.filter((c) => !c.problemas.length);

  async function confirmar() {
    const resultado = await clientesApi.importarClientes(importables);
    onImportados();
    return resultado;
  }

  return (
    <DialogoImportar
      titulo="Importar clientes"
      ayuda="Para corregir clientes que ya existen, parte del padrón actual: la columna ID —o el número de documento— es la que le dice al sistema cuál actualizar. El nombre se toma tal cual: esta carga no consulta a SUNAT ni a RENIEC."
      rutaPlantilla={RUTA_PLANTILLA_CLIENTES}
      rutaExportar={RUTA_EXPORTAR_CLIENTES}
      onAbrir={abrir}
      onValidar={revisar}
      onConfirmar={confirmar}
      importables={importables.length}
    >
      {revision && <Revision revision={revision} clientes={clientes} />}
    </DialogoImportar>
  );
}

function Revision({
  revision,
  clientes,
}: {
  revision: RevisionClientes;
  clientes: ClienteRevisado[];
}) {
  const conProblema = clientes.filter((c) => c.problemas.length);
  const aActualizar = clientes.filter(
    (c) => c.accion === "actualizar" && !c.problemas.length,
  );

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-dark">
        <strong>{revision.listas}</strong> nuevo(s)
        {aActualizar.length > 0 && (
          <>
            {" · "}
            <strong>{aActualizar.length}</strong> a actualizar
          </>
        )}
        {conProblema.length > 0 && (
          <>
            {" · "}
            <span className="text-secondary">
              {conProblema.length} con problemas
            </span>
          </>
        )}
      </p>

      {aActualizar.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold text-dark">
            Clientes que ya existen y se van a actualizar
          </p>
          {aActualizar.map((c) => (
            <p key={c.fila} className="text-xs text-gray">
              {c.nombre}
              {c.cambios.length > 0 && <> — {c.cambios.join(" · ")}</>}
            </p>
          ))}
        </div>
      )}

      {conProblema.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold text-dark">
            Filas que no se van a importar
          </p>
          <p className="text-xs text-gray">
            Los datos de un cliente natural se corrigen en su ficha de persona,
            no acá (RN-GEN-007).
          </p>
          {conProblema.map((c) => (
            <p key={`${c.fila}-${c.nombre}`} className="text-xs text-gray">
              <span className="font-mono">Fila {c.fila}</span> · {c.nombre} —{" "}
              <span className="text-secondary">{c.problemas.join("; ")}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
