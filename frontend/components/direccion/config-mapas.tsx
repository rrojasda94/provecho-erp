"use client";

import { createContext, useContext } from "react";

export type ConfigMapas = {
  /** Clave del navegador. Vacía = campos de dirección sin mapa. */
  apiKey: string;
  /** Map ID de la consola de Google (`DEMO_MAP_ID` sirve en desarrollo). */
  mapId: string;
  /** Sesgo del autocompletado (ISO 3166-1 alfa-2). */
  pais: string;
};

export const CONFIG_APAGADA: ConfigMapas = { apiKey: "", mapId: "", pais: "pe" };

const Contexto = createContext<ConfigMapas>(CONFIG_APAGADA);

/**
 * La configuración de Maps baja una vez desde el layout, no por props.
 *
 * La clave la lee el proceso de Next (`process.env`), que un Client Component
 * no puede tocar. Pasarla como prop obligaría a tocar las seis páginas que
 * tienen un campo de dirección **y** los seis componentes cliente que
 * cuelgan de ellas, y la séptima pantalla se olvidaría. Acá se declara una
 * vez y `CampoDireccion` la encuentra sola.
 *
 * No es `NEXT_PUBLIC_*` justamente por esto: esa familia se hornea en el
 * build (ver `docs/engineering/devops.md`), y así la clave se puede cambiar
 * reiniciando el contenedor en vez de reconstruyendo la imagen.
 */
export function ProveedorConfigMapas({
  config,
  children,
}: {
  config: ConfigMapas;
  children: React.ReactNode;
}) {
  return <Contexto.Provider value={config}>{children}</Contexto.Provider>;
}

export function useConfigMapas(): ConfigMapas {
  return useContext(Contexto);
}
