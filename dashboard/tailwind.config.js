/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg:       '#000000',
        surface:  '#0A0A0A',
        surface2: '#111111',
        border:   '#1A1A1A',
        border2:  '#222222',
        green:    '#00FF88',
        red:      '#FF3355',
        poly:     '#7B3FE4',
        kalshi:   '#0066FF',
        text:     '#FFFFFF',
        muted:    '#666666',
        dim:      '#333333',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
