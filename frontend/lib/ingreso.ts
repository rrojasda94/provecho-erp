/**
 * Entrada a las apps instalables (ADR-109): KDS, PDV y Mi reparto se
 * instalan en Android como tres apps separadas, cada una con `scope` propio.
 * Un `/login` fijo quedaba fuera de ese scope —Android lo abre con barra de
 * navegador— y al entrar mandaba al home del ERP, no de vuelta a la app.
 *
 * Por eso cada app tiene su `/<app>/ingresar` (un rewrite a `/login`, ver
 * `next.config.mjs`) y el `next` que la devuelve a donde estaba.
 *
 * Sin imports de Next: lo usa `ingreso.test.ts` con `node --test`.
 */

/**
 * Destinos post-login aceptados. Regex exacta —no basta con no ser
 * absoluta— porque `next` sale de la URL y un valor cualquiera ahí sería un
 * open redirect. `/oauth/authorize` es la mitad del SSO del BI (ADR-083).
 */
export const SIGUIENTE_PERMITIDO = /^\/(oauth\/authorize|kds|pdv|reparto)(\?[^\s]*)?$/;

const APPS_INSTALABLES = ["/kds", "/pdv", "/reparto"] as const;
export type AppInstalable = (typeof APPS_INSTALABLES)[number];

/** Guard para lo que llega del cliente (una server action lo recibe). */
export function esAppInstalable(valor: unknown): valor is AppInstalable {
  return APPS_INSTALABLES.includes(valor as AppInstalable);
}

function ingresoA(app: AppInstalable, destino: string): string {
  return `${app}/ingresar?next=${encodeURIComponent(destino)}`;
}

/** `/kds/ingresar?next=/kds?pantalla=…`: vuelve a la misma pantalla. */
export function urlIngreso(
  app: AppInstalable,
  parametros: Record<string, string | undefined> = {},
): string {
  const definidos = Object.entries(parametros).filter(
    (par): par is [string, string] => par[1] !== undefined,
  );
  const consulta = new URLSearchParams(definidos).toString();
  return ingresoA(app, consulta ? `${app}?${consulta}` : app);
}

/**
 * Lo mismo desde el cliente, con `location`: dentro de una app vuelve a
 * ella; en cualquier otra pantalla, el `/login` de siempre.
 */
export function ingresoDesde(ruta: string, consulta: string): string {
  const app = APPS_INSTALABLES.find((a) => ruta === a || ruta.startsWith(`${a}/`));
  return app ? ingresoA(app, app + consulta) : "/login";
}
