/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          deep: '#090d16',
          surface: '#0f172a',
          elevated: '#1e293b',
          highlight: '#334155',
        },
        border: {
          subtle: '#1e293b',
          muted: '#334155',
          active: '#475569',
        },
        brand: {
          DEFAULT: '#0284c7', // sky-600
          hover: '#0369a1',
          light: '#38bdf8',
          accent: '#06b6d4',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
