/** @type {import('tailwindcss').Config} */
export default {
	content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
	theme: {
		extend: {
			fontFamily: {
				sans: ['Inter', 'ui-sans-serif', 'system-ui'],
				display: ['Barlow Condensed', 'ui-sans-serif'],
				mono: ['JetBrains Mono', 'ui-monospace'],
			},
			colors: {
				f1red: '#E8002D',
				surface: '#0d1220',
				panel: '#111827',
				border: '#1e2a3a',
				muted: '#3d4f66',
				dim: '#8899aa',
				gold: '#FFD700',
				silver: '#C0C0C0',
				bronze: '#CD7F32',
			},
			animation: {
				'glow': 'glow 2s ease-in-out infinite alternate',
				'scan': 'scan 12s linear infinite',
				'fadeUp': 'fadeUp 0.5s ease-out forwards',
			},
			keyframes: {
				glow: {
					'0%': { opacity: '0.5', transform: 'scale(1)' },
					'100%': { opacity: '1', transform: 'scale(1.02)' },
				},
				scan: {
					'0%': { backgroundPosition: '0 -200%' },
					'100%': { backgroundPosition: '0 200%' },
				},
				fadeUp: {
					'0%': { opacity: '0', transform: 'translateY(12px)' },
					'100%': { opacity: '1', transform: 'translateY(0)' },
				},
			},
		}
	},
	plugins: []
}
