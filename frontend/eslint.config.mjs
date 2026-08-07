import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

// Reemplaza a `.eslintrc.json`. No es una preferencia de estilo: ESLint 10
// eliminó la dependencia `@eslint/eslintrc`, así que el formato viejo ya no
// existe para él, y `eslint-config-next` 16 solo publica configuración plana.
// Mantener el `.eslintrc.json` era lo que hacía fallar `npm run lint` en main
// con "Converting circular structure to JSON".
export default [
  // `next lint` descartaba estas rutas por su cuenta; el CLI de ESLint no
  // sabe nada de ellas y sin esto intenta analizar el build entero.
  {
    ignores: [
      ".next/**",
      "out/**",
      "next-env.d.ts",
      "test-results/**",
      "playwright-report/**",
    ],
  },

  ...coreWebVitals,
  ...typescript,

  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      complexity: ["error", 10],
    },
  },

  // Los componentes de shadcn/ui llegan generados: su complejidad no es una
  // decisión nuestra y reescribirlos rompe el `npx shadcn add` siguiente.
  {
    files: ["components/ui/**"],
    rules: { complexity: "off" },
  },

  // Un `export default` anónimo es la forma que estos archivos de
  // configuración documentan: nombrar la variable solo para satisfacer la
  // regla no le dice nada a nadie. `next lint` nunca los analizó.
  {
    files: ["*.mjs", "*.config.ts"],
    rules: { "import/no-anonymous-default-export": "off" },
  },

  // `eslint-plugin-react-hooks` 7 (entra con eslint-config-next 16) suma las
  // reglas del React Compiler. Son 34 hallazgos reales repartidos en 30
  // archivos: 18 de Server Components que arman JSX dentro de un `try`, 16 de
  // `setState` en el cuerpo de un `useEffect`. Quedan en `warn` a propósito —
  // se ven en cada corrida pero no bloquean — porque arreglarlos es refactor
  // de la capa de datos del frontend, no parte de subir de major.
  // Ver ROADMAP -> Deuda técnica -> Frontend.
  {
    rules: {
      "react-hooks/error-boundaries": "warn",
      "react-hooks/set-state-in-effect": "warn",
    },
  },
];
