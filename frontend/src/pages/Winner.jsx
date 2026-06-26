import { useEffect, useState } from 'react'
import {
	BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell
} from 'recharts'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function Winner() {
	const [years, setYears] = useState([])
	const [gps, setGps] = useState([])
	const [year, setYear] = useState(2023)
	const [gp, setGp] = useState('')
	const [predictions, setPredictions] = useState([])
	const [raceInfo, setRaceInfo] = useState({ race: '', year: 0 })
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState('')

	// Load years
	useEffect(() => {
		(async () => {
			try {
				const r = await fetch(`${API_BASE}/years`)
				const d = await r.json()
				setYears(d.years || [])
				if (!year && d.years?.length) setYear(d.years[d.years.length - 1])
			} catch {}
		})()
	}, [])

	// Load GP list for year
	useEffect(() => {
		(async () => {
			try {
				const url = new URL(`${API_BASE}/metadata`)
				url.searchParams.set('year', String(year))
				const r = await fetch(url)
				const d = await r.json()
				setGps(d.gps || [])
				if (!gp && (d.gps?.length)) setGp(d.gps[0])
			} catch {}
		})()
	}, [year])

	// Auto-load predictions when GP changes
	useEffect(() => {
		if (gp && year) {
			fetchPredictions()
		}
	}, [gp, year])

	const fetchPredictions = async () => {
		if (!gp || !year) return
		setLoading(true)
		setError('')
		try {
			const url = new URL(`${API_BASE}/predict-winner`)
			url.searchParams.set('year', String(year))
			url.searchParams.set('gp', gp)
			const res = await fetch(url)
			if (!res.ok) throw new Error(await res.text())
			const data = await res.json()
			setPredictions(data.predictions || [])
			setRaceInfo({ race: data.race || '', year: data.year || year })
		} catch (err) {
			setError(String(err))
			setPredictions([])
			setRaceInfo({ race: '', year: 0 })
		} finally {
			setLoading(false)
		}
	}

	// Calculate chaos probability from probability distribution
	// Higher entropy = more chaos (probabilities are more evenly distributed)
	const calculateChaosProbability = () => {
		if (predictions.length === 0) return 0.0
		
		// Calculate entropy of the probability distribution
		let entropy = 0
		for (const pred of predictions) {
			const prob = pred.win_probability
			if (prob > 0) {
				entropy -= prob * Math.log2(prob)
			}
		}
		
		// Normalize: max entropy is log2(n) where n is number of drivers
		const maxEntropy = Math.log2(predictions.length)
		const normalizedEntropy = maxEntropy > 0 ? entropy / maxEntropy : 0
		
		// Also consider spread: if top 3 probabilities are close, higher chaos
		if (predictions.length >= 3) {
			const top3Probs = predictions.slice(0, 3).map(p => p.win_probability)
			const spread = Math.max(...top3Probs) - Math.min(...top3Probs)
			// Low spread = high chaos (probabilities are close together)
			const spreadFactor = 1.0 - Math.min(1.0, spread * 2) // Normalize spread
			
			// Combine entropy and spread
			return Math.min(1.0, (normalizedEntropy * 0.6 + spreadFactor * 0.4))
		}
		
		return normalizedEntropy
	}

	const chaosProbability = calculateChaosProbability()

	// Color gradient for probabilities
	const getColor = (prob, rank) => {
		// Highlight top 3
		if (rank <= 3) {
			if (rank === 1) return '#e10600' // F1 red for #1
			if (rank === 2) return '#ff6b00' // Orange for #2
			if (rank === 3) return '#ffa500' // Gold for #3
		}
		// Others
		if (prob >= 0.15) return '#ffa500' // Orange for medium-high
		if (prob >= 0.05) return '#ffb84d' // Light orange for medium
		return '#666' // Gray for low
	}

	// Get chaos indicator color
	const getChaosColor = (chaos) => {
		if (chaos >= 0.7) return '#e10600' // Red - high chaos
		if (chaos >= 0.4) return '#ff6b00' // Orange - medium chaos
		return '#4ade80' // Green - low chaos
	}

	return (
		<div>
			<h2 className="text-2xl font-bold text-primary mb-4">Grand Prix Winner Prediction</h2>
			
			<div className="card mb-4 grid grid-cols-1 md:grid-cols-3 gap-3">
				<label className="label">
					Year
					<select className="input" value={year} onChange={e => setYear(Number(e.target.value))}>
						{years.map(y => <option key={y} value={y}>{y}</option>)}
					</select>
				</label>
				<label className="label">
					Grand Prix
					<select className="input" value={gp} onChange={e => setGp(e.target.value)}>
						{gps.map((g, i) => <option key={i} value={g}>{g}</option>)}
					</select>
				</label>
				<button className="btn" onClick={fetchPredictions} disabled={loading || !gp}>
					{loading ? 'Loading...' : 'Refresh'}
				</button>
			</div>

			{error && <div className="card text-red-400 mb-4 whitespace-pre-wrap">{error}</div>}

			{predictions.length === 0 ? (
				<div className="card text-neutral-300">No predictions available. Select a Grand Prix and click Refresh.</div>
			) : (
				<>
					{/* Chaos Probability Indicator */}
					<div className="card mb-4">
						<div className="flex items-center justify-between">
							<div>
								<h3 className="text-lg font-semibold mb-1">Race Chaos Probability</h3>
								<p className="text-sm text-neutral-400">
									{chaosProbability >= 0.7 ? 'High chaos - unpredictable race expected' :
									 chaosProbability >= 0.4 ? 'Medium chaos - some unpredictability' :
									 'Low chaos - more predictable outcome'}
								</p>
							</div>
							<div className="text-right">
								<div 
									className="text-4xl font-bold"
									style={{ color: getChaosColor(chaosProbability) }}
								>
									{(chaosProbability * 100).toFixed(0)}%
								</div>
								<div className="text-xs text-neutral-400 mt-1">Chaos Index</div>
							</div>
						</div>
						{/* Progress bar */}
						<div className="mt-3 h-2 bg-neutral-800 rounded-full overflow-hidden">
							<div 
								className="h-full transition-all duration-300"
								style={{ 
									width: `${chaosProbability * 100}%`,
									backgroundColor: getChaosColor(chaosProbability)
								}}
							/>
						</div>
					</div>

					{/* Ranked Table */}
					<div className="card mb-6 overflow-auto">
						<h3 className="text-lg font-semibold mb-4">
							{raceInfo.race} {raceInfo.year} - Winner Predictions
						</h3>
						<table className="w-full text-left text-sm">
							<thead className="text-neutral-400">
								<tr>
									<th>Rank</th>
									<th>Driver</th>
									<th>Win Probability</th>
									<th>Visual</th>
								</tr>
							</thead>
							<tbody>
								{predictions.map((p, i) => {
									const rank = i + 1
									const isTop3 = rank <= 3
									return (
										<tr 
											key={i} 
											className={`border-t border-neutral-800 ${isTop3 ? 'bg-neutral-900/50' : ''}`}
										>
											<td className="font-semibold">
												{rank === 1 && '🥇 '}
												{rank === 2 && '🥈 '}
												{rank === 3 && '🥉 '}
												{rank}
											</td>
											<td className={`font-medium ${isTop3 ? 'text-primary' : ''}`}>
												{p.driver}
											</td>
											<td>
												<span 
													className="font-semibold" 
													style={{ color: getColor(p.win_probability, rank) }}
												>
													{(p.win_probability * 100).toFixed(1)}%
												</span>
											</td>
											<td>
												<div className="w-32 h-4 bg-neutral-800 rounded-full overflow-hidden">
													<div 
														className="h-full transition-all duration-300"
														style={{ 
															width: `${p.win_probability * 100}%`,
															backgroundColor: getColor(p.win_probability, rank)
														}}
													/>
												</div>
											</td>
										</tr>
									)
								})}
							</tbody>
						</table>
					</div>

					{/* Horizontal Bar Chart */}
					<div className="card">
						<h3 className="text-lg font-semibold mb-4">Win Probability Chart (Top 10)</h3>
						<div className="h-96">
							<ResponsiveContainer width="100%" height="100%">
								<BarChart 
									data={predictions.slice(0, 10)} 
									layout="vertical"
									margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
								>
									<CartesianGrid strokeDasharray="3 3" stroke="#333" />
									<XAxis 
										type="number" 
										domain={[0, 1]}
										stroke="#bbb"
										tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
									/>
									<YAxis 
										type="category" 
										dataKey="driver" 
										stroke="#bbb"
										width={70}
									/>
									<Tooltip 
										formatter={(value) => `${(value * 100).toFixed(1)}%`}
										contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
									/>
									<Legend />
									<Bar dataKey="win_probability" name="Win Probability" radius={[0, 4, 4, 0]}>
										{predictions.slice(0, 10).map((entry, index) => (
											<Cell 
												key={`cell-${index}`} 
												fill={getColor(entry.win_probability, index + 1)} 
											/>
										))}
									</Bar>
								</BarChart>
							</ResponsiveContainer>
						</div>
					</div>
				</>
			)}
		</div>
	)
}
