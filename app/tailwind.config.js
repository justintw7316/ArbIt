/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: '#060810',
        surface: '#0d1117',
        border: '#1a2040',
        orange: '#ff6b35',
        cyan: '#4fc3f7',
        amber: '#ff9800',
        purple: '#a78bfa',
        green: '#00e676',
        red: '#ff3b3b',
        'text-primary': '#ffffff',
        'text-secondary': '#94a3b8',
        'text-muted': '#4a5568',
      },
      fontFamily: {
        mono: ['"Courier New"', 'Courier', 'monospace'],
      },
    },
  },
  plugins: [],
}

