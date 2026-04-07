import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './hooks/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        navy:        '#0D1B2A',
        'navy-mid':  '#162538',
        'navy-light':'#1E3350',
        slate:       '#2E4A6B',
        blue: {
          DEFAULT: '#1B6CA8',
          bright:  '#2482CC',
        },
        cyan: {
          DEFAULT: '#00C2E0',
        },
        teal:  '#0EA5A0',
        gold:  '#E8B84B',
        green: '#22C55E',
        red:   '#EF4444',
        amber: '#F59E0B',
        muted: '#94A3B8',
      },
      fontFamily: {
        sans:    ['DM Sans', 'sans-serif'],
        mono:    ['DM Mono', 'monospace'],
        display: ['Playfair Display', 'serif'],
      },
      borderRadius: {
        DEFAULT: '10px',
        lg:      '16px',
      },
    },
  },
  plugins: [],
}
export default config
