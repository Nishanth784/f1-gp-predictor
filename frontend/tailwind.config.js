/** @type {import('tailwindcss').Config} */
export default {
	content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
	theme: {
		extend: {
			fontFamily: {
				sans: ['Inter', 'ui-sans-serif', 'system-ui'],
				display: ['Rajdhani', 'Inter', 'ui-sans-serif']
			},
			colors: {
				primary: "#e10600",
			},
			backgroundImage: {
				'f1-hero': 'radial-gradient(1200px 600px at 70% -10%, rgba(225,6,0,0.25), transparent), radial-gradient(800px 400px at 10% 10%, rgba(255,255,255,0.06), transparent)'
			}
		}
	},
	plugins: []
};
