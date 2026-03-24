import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
    './hooks/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#10a37f',
        'primary-hover': '#0d8c6d',
        surface: {
          DEFAULT: '#111111',
          2: '#161616',
          3: '#1a1a1a',
          4: '#1e1e1e',
        },
        border: {
          DEFAULT: '#2d2d2d',
          light: '#333333',
        },
        text: {
          DEFAULT: '#e8e8e8',
          muted: '#888888',
          faint: '#555555',
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

export default config
