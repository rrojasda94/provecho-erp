import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

// Mismo motivo que frontend/eslint.config.mjs: ESLint 10 quitó soporte del
// formato .eslintrc, y eslint-config-next 16 solo publica config plana.
export default [
  { ignores: [".next/**", "out/**", "next-env.d.ts"] },

  ...coreWebVitals,
  ...typescript,

  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },

  {
    files: ["*.mjs", "*.config.ts"],
    rules: { "import/no-anonymous-default-export": "off" },
  },
];
