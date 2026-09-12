import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef4ff',
          100: '#dce7fe',
          200: '#c0d3fd',
          300: '#94b6fb',
          400: '#6191f6',
          500: '#3d6def',
          600: '#274de3',
          700: '#1f3bd1',
          800: '#2033a9',
          900: '#1f3086',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
} as Config;
