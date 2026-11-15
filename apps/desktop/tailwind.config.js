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
          deep: '#0A0A0A',      // True Deep Black
          surface: '#141414',   // Matte Carbon Panel
          elevated: '#1C1C1C',  // Raised Technical Panel
          highlight: '#262626', // Hover highlight
        },
        border: {
          subtle: '#262626',    // Crisp 1px structural line
          muted: '#333333',     // Defined component boundary
          active: '#FF3B30',    // Signal Red active focus
        },
        brand: {
          DEFAULT: '#FF3B30',   // Signal Industrial Red
          hover: '#E02D22',     // Deep Signal Red on hover
          light: '#FF6961',     // Light Red accent
          accent: '#FF3B30',    // Focus Red
        },
      },
      fontFamily: {
        sans: ['"Space Grotesk"', 'Segoe UI', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"Space Grotesk"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '2px',
        sm: '2px',
        md: '4px',
        lg: '6px',
        xl: '8px',
      },
    },
  },
  plugins: [],
}
