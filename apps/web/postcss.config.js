// Tailwind runs as a PostCSS plugin; autoprefixer adds vendor prefixes.
// ESM syntax because package.json sets "type": "module".
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
