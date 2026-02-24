import Navbar from '../components/Navbar'

export default function Home() {
	return (
		<div className="min-h-screen bg-black text-white">
			<Navbar />
			<header className="hero">
				<div className="max-w-6xl mx-auto px-6 py-16 md:py-24">
					<h1 className="title text-5xl md:text-6xl font-extrabold leading-tight">
						Predict <span className="text-primary">F1</span> Lap Times
					</h1>
					<p className="text-neutral-300 mt-4 max-w-2xl">
						Data-driven predictions with FastF1 and scikit-learn. Predict lap times, compare actual vs predicted, and predict Grand Prix winners.
					</p>
					<div className="mt-8 flex gap-3">
						<a href="/predict" className="btn">Start Predicting</a>
						<a href="/compare" className="btn-outline">Open Dashboard</a>
						<a href="/winner" className="btn-outline">Predict Winner</a>
					</div>
				</div>
			</header>
			<main className="max-w-6xl mx-auto px-6 py-10 grid md:grid-cols-3 gap-6">
				<div className="panel-glass p-6">
					<h3 className="title text-xl mb-2">FastF1 Integration</h3>
					<p className="text-neutral-300">Pull laps and weather data per session with caching for faster analysis.</p>
				</div>
				<div className="panel-glass p-6">
					<h3 className="title text-xl mb-2">Feature Engineering</h3>
					<p className="text-neutral-300">Sector normalization, DriverTeam encoding, tyre age proxy, and track evolution.</p>
				</div>
				<div className="panel-glass p-6">
					<h3 className="title text-xl mb-2">Modeling</h3>
					<p className="text-neutral-300">Train multiple regressors for lap times and classifiers for winner prediction. Compare metrics and save the best models.</p>
				</div>
			</main>
		</div>
	)
}
