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
        'deep-night': 'var(--bg-primary)',
        'card-bg': 'var(--bg-card)',
        'border-dark': 'var(--border-color)',
        'cp-high': 'var(--cp-high)',
        'cp-mid': 'var(--cp-mid)',
        'cp-low': 'var(--cp-low)',
        'cp-unknown': '#666666',
        'accent-blue': 'var(--accent-blue)',
        'accent-purple': '#a855f7',
        'text-primary': 'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace'],
      }
    },
  },
  plugins: [],
}
