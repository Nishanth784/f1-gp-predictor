import { Link, useLocation } from 'react-router-dom'

export default function Navbar() {
	const { pathname } = useLocation()
	const link = (to, label) => (
		<Link to={to} className={`btn-ghost ${pathname===to?'bg-neutral-800 text-white':'text-neutral-300'}`}>{label}</Link>
	)
	return (
		<nav className="w-full bg-black/80 border-b border-neutral-800 backdrop-blur">
			<div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
				<Link to="/" className="title text-lg text-primary tracking-wide">F1 Predictor</Link>
				<div className="flex gap-2">
					{link('/', 'Home')}
					{link('/predict', 'Predict')}
					{link('/compare', 'Compare')}
					{link('/winner', 'Winner')}
				</div>
			</div>
		</nav>
	)
}
