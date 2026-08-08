import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // CarbonSense brand palette — deep green (ESG theme)
        primary: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a', // main brand green
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
        },
        // Scope colours — consistent across all charts
        scope1: '#ef4444', // red — direct (most controllable)
        scope2: '#f59e0b', // amber — indirect energy
        scope3: '#8b5cf6', // purple — value chain (largest)
        // Status colours
        anomaly: '#dc2626',
        warning: '#d97706',
        healthy: '#16a34a',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config
