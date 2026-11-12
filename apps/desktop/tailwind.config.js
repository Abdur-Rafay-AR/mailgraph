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
          deep: '#0c0814',
          surface: '#140e26',
          elevated: '#1f1638',
          highlight: '#2d2050',
        },
        border: {
          subtle: '#261a46',
          muted: '#3d2b6e',
          active: '#6d45ba',
        },
        brand: {
          DEFAULT: '#9061f9', // violet-500
          hover: '#7e3af2',   // violet-600
          light: '#c084fc',   // violet-400
          accent: '#e879f9',  // fuchsia-400
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
