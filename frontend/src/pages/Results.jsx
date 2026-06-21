import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, RefreshCw, AlertTriangle } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8011'

// ─── Team color mapping ─────────────────────────────────────────────────────
const TEAM_COLORS = {
	'ferrari':              '#E8002D',
	'mercedes':             '#00D2BE',
	'red bull racing':      '#3671C6',
	'red bull':             '#3671C6',
	'mclaren':              '#FF8000',
	'aston martin':         '#358C75',
	'alpine':               '#FF87BC',
	'williams':             '#64C4FF',
	'haas f1 team':         '#B6BABD',
	'haas':                 '#B6BABD',
	'alphatauri':           '#6692FF',
	'rb':                   '#6692FF',
	'visa cash app rb':     '#6692FF',
	'racing bulls':         '#6692FF',
	'alfa romeo':           '#900000',
	'kick sauber':          '#52E252',
	'sauber':               '#52E252',
	'renault':              '#FFF500',
	'racing point':         '#F596C8',
	'force india':          '#F596C8',
	'toro rosso':           '#469BFF',
}

function getTeamColor(team = '') {
	return TEAM_COLORS[team.toLowerCase()] || '#8899aa'
}

// ─── Circuit SVG watermarks ─────────────────────────────────────────────────
const CIRCUITS = {
	monaco: (
		<path d="M160,20 L200,22 C220,23 235,35 238,55 L240,90 L232,110 C226,125 215,132 202,135 L185,137 L165,160 C155,172 140,178 125,175 L90,168 L65,148 C50,135 44,118 48,100 L55,75 L45,55 C40,40 45,25 58,18 L80,14 Z"
			fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
	),
	silverstone: (
		<path d="M50,80 C50,40 90,15 140,20 L200,30 C225,35 240,55 238,80 L232,115 C228,140 210,158 185,162 L140,168 C115,170 95,160 78,142 L58,115 Z"
			fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
	),
	monza: (
		<path d="M60,50 L180,50 C200,50 215,65 215,85 L215,140 C215,160 200,175 180,175 L60,175 C40,175 25,160 25,140 L25,120 L120,120 L120,105 L25,105 L25,85 C25,65 40,50 60,50 Z"
			fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
	),
	spa: (
		<path d="M40,80 L90,30 C105,15 125,12 145,22 L190,45 C210,55 220,75 215,98 L205,140 C198,162 178,175 155,172 L100,165 C75,160 55,145 50,120 Z"
			fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
	),
	suzuka: (
		<path d="M80,30 L160,30 C180,30 195,45 195,65 L195,95 L130,95 L130,115 L195,115 L195,145 C195,165 180,180 160,180 L80,180 C60,180 45,165 45,145 L45,65 C45,45 60,30 80,30 Z"
			fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
	),
	bahrain: (
		<path d="M55,70 L125,30 C145,20 168,22 185,38 L215,70 C228,85 228,105 215,120 L185,152 C168,168 145,170 125,160 L55,120 C38,108 32,90 40,74 Z"
			fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
	),
	default: (
		<path d="M45,90 C45,55 72,28 110,25 L155,25 C190,25 215,50 215,85 L215,110 C215,145 190,170 155,170 L110,170 C72,170 45,145 45,110 Z"
			fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
	),
}

function getCircuit(gpName = '') {
	const n = gpName.toLowerCase()
	if (n.includes('monaco'))     return CIRCUITS.monaco
	if (n.includes('silverstone') || n.includes('british')) return CIRCUITS.silverstone
	if (n.includes('monza')  || n.includes('italian'))      return CIRCUITS.monza
	if (n.includes('spa')    || n.includes('belgian'))      return CIRCUITS.spa
	if (n.includes('suzuka') || n.includes('japanese'))     return CIRCUITS.suzuka
	if (n.includes('bahrain'))    return CIRCUITS.bahrain
	return CIRCUITS.default
}

// ─── Count-up hook ──────────────────────────────────────────────────────────
function useCountUp(target, duration = 1200, trigger = false) {
	const [value, setValue] = useState(0)
	const raf = useRef(null)

	useEffect(() => {
		if (!trigger) return
		const start = performance.now()
		const tick = (now) => {
			const t = Math.min((now - start) / duration, 1)
			const ease = 1 - Math.pow(1 - t, 3)
			setValue(target * ease)
			if (t < 1) raf.current = requestAnimationFrame(tick)
		}
		raf.current = requestAnimationFrame(tick)
		return () => cancelAnimationFrame(raf.current)
	}, [target, trigger, duration])

	return value
}

// ─── Animated probability bar ───────────────────────────────────────────────
function ProbBar({ probability, color, delay = 0, triggered }) {
	const pct = (probability * 100).toFixed(1)
	const count = useCountUp(probability * 100, 1200, triggered)

	return (
		<div className="flex items-center gap-3">
			<div className="font-mono text-sm font-bold w-12 text-right" style={{ color }}>
				{triggered ? count.toFixed(1) : '0.0'}%
			</div>
			<div className="prob-bar-track flex-1">
				<div
					className="prob-bar-fill"
					style={{
						width: triggered ? `${pct}%` : '0%',
						background: color,
						transitionDelay: `${delay}ms`,
					}}
				/>
			</div>
		</div>
	)
}

// ─── Podium card (P1/P2/P3) ─────────────────────────────────────────────────
function PodiumCard({ pred, rank, triggered }) {
	const color = getTeamColor(pred.team)
	const podiumColor = rank === 1 ? 'var(--gold)' : rank === 2 ? 'var(--silver)' : 'var(--bronze)'
	const podiumLabel = rank === 1 ? 'P1 · POLE FAVOURITE' : rank === 2 ? 'P2' : 'P3'
	const count = useCountUp(pred.win_probability * 100, 1400, triggered)
	const isFirst = rank === 1

	return (
		<div
			className="podium-card flex flex-col"
			style={{
				'--podium-color': podiumColor,
				order: rank === 2 ? -1 : rank === 3 ? 1 : 0,
				padding: isFirst ? '24px 20px' : '18px 16px',
				boxShadow: isFirst ? `0 0 40px rgba(0,0,0,0.5), 0 0 20px ${color}22` : undefined,
				border: isFirst ? `1px solid ${color}44` : undefined,
			}}
		>
			{/* Podium medal */}
			<div className="telem-label mb-3" style={{ color: podiumColor }}>{podiumLabel}</div>

			{/* Team accent strip */}
			<div style={{ width: 32, height: 4, background: color, borderRadius: 2, marginBottom: 14 }} />

			{/* Driver code */}
			<div
				className="font-display font-bold leading-none mb-1"
				style={{ fontSize: isFirst ? '3.5rem' : '2.8rem', color: '#fff', letterSpacing: '-0.01em' }}
			>
				{pred.driver}
			</div>

			{/* Team name */}
			<div className="font-mono text-xs mb-4" style={{ color }}>
				{pred.team || '—'}
			</div>

			{/* Win probability */}
			<div className="mt-auto">
				<div className="telem-label mb-1">WIN PROBABILITY</div>
				<div className="font-display font-bold" style={{ fontSize: isFirst ? '2.4rem' : '1.9rem', color }}>
					{triggered ? count.toFixed(1) : '0.0'}%
				</div>
				<div className="prob-bar-track mt-2">
					<div
						className="prob-bar-fill"
						style={{ width: triggered ? `${pred.win_probability * 100}%` : '0%', background: color }}
					/>
				</div>
			</div>

			{/* Grid position badge */}
			{pred.grid_position != null && (
				<div className="mt-3 font-mono text-xs text-[#3d4f66]">
					GRID P{pred.grid_position}
				</div>
			)}
		</div>
	)
}

// ─── Driver list row ─────────────────────────────────────────────────────────
function DriverRow({ pred, rank, triggered, delay }) {
	const color = getTeamColor(pred.team)

	return (
		<div
			className="driver-row flex items-center gap-4 py-3 px-4 animate-fadeUp"
			style={{ animationDelay: `${delay}ms`, animationFillMode: 'both' }}
		>
			{/* Rank */}
			<div className="rank-badge text-[#3d4f66]" style={{ width: 28 }}>
				{rank}
			</div>

			{/* Team color swatch */}
			<div style={{ width: 3, height: 36, background: color, borderRadius: 2, flexShrink: 0 }} />

			{/* Driver info */}
			<div style={{ width: 80, flexShrink: 0 }}>
				<div className="font-display font-bold text-white text-xl leading-tight">{pred.driver}</div>
				<div className="font-mono text-[0.6rem] truncate" style={{ color, maxWidth: 80 }}>{pred.team || '—'}</div>
			</div>

			{/* Bar */}
			<div className="flex-1">
				<ProbBar
					probability={pred.win_probability}
					color={color}
					delay={delay}
					triggered={triggered}
				/>
			</div>

			{/* Grid */}
			{pred.grid_position != null && (
				<div className="font-mono text-xs text-[#3d4f66] w-10 text-right flex-shrink-0">
					P{pred.grid_position}
				</div>
			)}
		</div>
	)
}

// ─── Results page ───────────────────────────────────────────────────────────
export default function Results() {
	const { year, gp } = useParams()
	const navigate = useNavigate()
	const gpDecoded = decodeURIComponent(gp)

	const [predictions, setPredictions] = useState([])
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState('')
	const [triggered, setTriggered] = useState(false)

	const fetchData = () => {
		setLoading(true)
		setError('')
		setTriggered(false)
		setPredictions([])

		fetch(`${API_BASE}/winner-probabilities?year=${year}&gp=${encodeURIComponent(gpDecoded)}`)
			.then(r => {
				if (!r.ok) return r.json().then(e => Promise.reject(e.detail || r.statusText))
				return r.json()
			})
			.then(d => {
				setPredictions(d.predictions || [])
				setLoading(false)
				// Trigger animations after a short mount delay
				setTimeout(() => setTriggered(true), 80)
			})
			.catch(err => {
				setError(typeof err === 'string' ? err : 'Failed to fetch predictions.')
				setLoading(false)
			})
	}

	useEffect(() => { fetchData() }, [year, gpDecoded])

	const top3 = predictions.slice(0, 3)
	const rest = predictions.slice(3)
	const circuit = getCircuit(gpDecoded)

	// Entropy-based chaos index
	const chaosIndex = (() => {
		if (predictions.length < 2) return 0
		let entropy = 0
		for (const p of predictions) {
			if (p.win_probability > 0) entropy -= p.win_probability * Math.log2(p.win_probability)
		}
		return Math.min(1, entropy / Math.log2(predictions.length))
	})()

	const chaosColor = chaosIndex > 0.65 ? '#E8002D' : chaosIndex > 0.4 ? '#FF8000' : '#00D2BE'

	return (
		<div className="relative min-h-screen" style={{ background: '#0a0e17' }}>
			<div className="scanlines" />

			{/* Circuit SVG watermark */}
			<div className="pointer-events-none fixed inset-0 z-0 flex items-center justify-end pr-8 opacity-[0.025]">
				<svg viewBox="0 0 280 200" style={{ width: 'min(60vw, 600px)', color: '#fff' }}>
					{circuit}
				</svg>
			</div>

			{/* Background glow */}
			<div className="pointer-events-none fixed inset-0 z-0">
				<div style={{
					position: 'absolute', top: '-30%', left: '-20%',
					width: '80vw', height: '80vw', maxWidth: 1000,
					background: 'radial-gradient(ellipse, rgba(232,0,45,0.05) 0%, transparent 60%)',
					borderRadius: '50%'
				}} />
			</div>

			{/* Nav bar */}
			<header className="relative z-10 border-b border-[#1e2a3a] px-4 py-3 flex items-center justify-between">
				<button
					onClick={() => navigate('/')}
					className="flex items-center gap-2 font-mono text-xs text-[#8899aa] hover:text-white transition-colors"
				>
					<ArrowLeft size={14} />
					BACK
				</button>

				<div className="flex items-center gap-3">
					<div style={{ width: 3, height: 22, background: '#E8002D', borderRadius: 1 }} />
					<span className="font-display font-bold tracking-widest text-sm uppercase text-white" style={{ letterSpacing: '0.15em' }}>
						F1 Predictor
					</span>
				</div>

				<button
					onClick={fetchData}
					disabled={loading}
					className="flex items-center gap-2 font-mono text-xs text-[#8899aa] hover:text-white transition-colors"
				>
					<RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
					REFRESH
				</button>
			</header>

			<main className="relative z-10 max-w-4xl mx-auto px-4 py-8">

				{/* Race header */}
				<div className="mb-8">
					<div className="f1-stripe mb-4" />
					<div className="font-mono text-xs text-[#E8002D] tracking-[0.3em] uppercase mb-2">
						{year} Formula 1 Season
					</div>
					<h1 className="font-display font-bold text-white leading-none uppercase"
						style={{ fontSize: 'clamp(2rem, 6vw, 4rem)', letterSpacing: '-0.01em' }}>
						{gpDecoded}
					</h1>
					<div className="font-mono text-xs text-[#3d4f66] mt-2 tracking-widest">
						WINNER PREDICTION · ML MODEL OUTPUT
					</div>
				</div>

				{/* Error */}
				{error && (
					<div className="panel flex items-start gap-3 p-4 mb-6 border-[#E8002D33]">
						<AlertTriangle size={16} className="text-[#E8002D] flex-shrink-0 mt-0.5" />
						<div>
							<div className="font-mono text-xs text-[#E8002D] mb-1 uppercase tracking-wider">Error</div>
							<div className="font-mono text-xs text-[#8899aa]">{error}</div>
							{error.includes('503') || error.includes('model') ? (
								<div className="font-mono text-xs text-[#3d4f66] mt-2">
									The winner model needs to be trained first. Run <code className="text-[#8899aa]">python main.py</code> in the project root.
								</div>
							) : null}
						</div>
					</div>
				)}

				{/* Loading */}
				{loading && (
					<div className="flex flex-col items-center justify-center py-24 gap-4">
						<div className="relative w-12 h-12">
							<div className="absolute inset-0 rounded-full border-2 border-[#1e2a3a]" />
							<div className="absolute inset-0 rounded-full border-2 border-transparent border-t-[#E8002D] animate-spin" />
						</div>
						<div className="font-mono text-xs text-[#3d4f66] tracking-widest uppercase">Fetching predictions…</div>
					</div>
				)}

				{!loading && predictions.length > 0 && (
					<>
						{/* Chaos + model info strip */}
						<div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-8">
							{[
								{
									label: 'CHAOS INDEX',
									value: `${(chaosIndex * 100).toFixed(0)}%`,
									color: chaosColor,
									sub: chaosIndex > 0.65 ? 'HIGH VARIANCE' : chaosIndex > 0.4 ? 'MODERATE' : 'PREDICTABLE'
								},
								{
									label: 'DRIVERS',
									value: predictions.length,
									color: '#8899aa',
									sub: 'IN FIELD'
								},
								{
									label: 'TOP PICK',
									value: predictions[0]?.driver ?? '—',
									color: getTeamColor(predictions[0]?.team),
									sub: predictions[0]?.team ?? '',
								},
							].map(({ label, value, color, sub }) => (
								<div key={label} className="panel p-3">
									<div className="telem-label mb-1">{label}</div>
									<div className="font-display font-bold text-2xl leading-none" style={{ color }}>{value}</div>
									<div className="telem-label mt-1">{sub}</div>
								</div>
							))}
						</div>

						{/* ── PODIUM ─────────────────────────────────────────────── */}
						<div className="mb-8">
							<div className="telem-label mb-4">// PODIUM PREDICTION</div>
							<div className="grid grid-cols-3 gap-3">
								{/* Render order: P2 | P1 | P3 — but on mobile just 3 cols */}
								{[top3[1], top3[0], top3[2]].map((pred, i) => {
									if (!pred) return <div key={i} />
									const realRank = i === 0 ? 2 : i === 1 ? 1 : 3
									return (
										<PodiumCard
											key={pred.driver}
											pred={pred}
											rank={realRank}
											triggered={triggered}
										/>
									)
								})}
							</div>
						</div>

						{/* ── FULL FIELD ─────────────────────────────────────────── */}
						{rest.length > 0 && (
							<div>
								<div className="telem-label mb-3">// FULL FIELD</div>
								<div className="panel overflow-hidden">
									{rest.map((pred, i) => (
										<DriverRow
											key={pred.driver}
											pred={pred}
											rank={i + 4}
											triggered={triggered}
											delay={i * 40}
										/>
									))}
								</div>
							</div>
						)}

						{/* Model footnote */}
						<div className="mt-8 font-mono text-[0.65rem] text-[#3d4f66] text-center leading-relaxed">
							Predictions generated by Gradient Boosting Classifier · Logistic Regression ensemble<br />
							Trained on {year === '2025' ? '2018–2024' : '2018–' + (parseInt(year) - 1)} qualifying, grid & historical data · Not financial or betting advice
						</div>
					</>
				)}
			</main>
		</div>
	)
}
