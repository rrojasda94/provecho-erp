/** Tailwind v4: el plugin de PostCSS se mudó a su propio paquete y el
 * prefijado de vendors ya lo hace Tailwind (autoprefixer sobra). */
export default {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
