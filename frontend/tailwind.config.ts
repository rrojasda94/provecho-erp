import type { Config } from "tailwindcss";

// ADR-013: Tailwind sobre los tokens de marca existentes (globals.css), sin
// hex mágico — cada color de Tailwind resuelve a una variable CSS que el PDV
// puede sobreescribir por marca.
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "var(--color-primary)",
        secondary: "var(--color-secondary)",
        dark: "var(--color-dark)",
        cream: "var(--color-cream)",
        accent: "var(--color-accent)",
        gray: "var(--color-gray)",
        background: "var(--color-background)",
        foreground: "var(--color-foreground)",
      },
      fontFamily: {
        heading: ["var(--font-heading)", "sans-serif"],
        body: ["var(--font-body)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "8px",
      },
    },
  },
  plugins: [],
} satisfies Config;
