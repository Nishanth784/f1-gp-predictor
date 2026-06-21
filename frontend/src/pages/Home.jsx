import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, Zap } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8011'

// ─── Custom dropdown ───────────────────────────────────────────────────────

function Select({ value, onChange, options, placeholder = 'Select…', disabled }) {
	const [open, setOpen] = useState(false)
	const ref = useRef(null)

	useEffect(() => {
		const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
		document.addEventListener('mousedown', handler)
		return () => document.removeEventListener('mousedown', handler)
	}, [])

	const label = options.find(o => String(o.value) === String(value))?.label ?? placeholder

	return (
		<div className="custom-select" ref={ref}>
			<div
				className={`custom-select-trigger${open ? ' open' : ''}${disabled ? ' opacity-40 pointer-events-none' : ''}`}
				onClick={() => !disabled && setOpen(v => !v)}
			>
				<span className={value ? 'text-white' : 'text-[#3d4f66]'}>{label}</span>
				<ChevronDown size={14} className={`text-[#3d4f66] transition-transform ${open ? 'rotate-180' : ''}`} />
			</div>
			{open && (
				<div className="custom-select-dropdown">
					{options.map(opt => (
						<div
							key={opt.value}
							className={`custom-select-option${String(opt.value) === String(value) ? ' selected' : ''}`}
							onClick={() => { onChange(opt.value); setOpen(false) }}
						>
							{opt.label}
						</div>
					))}
				</div>
			)}
		</div>
	)
}

// ─── Home ──────────────────────────────────────────────────────────────────

export default function Home() {
	const navigate = useNavigate()
	const [years, setYears] = useState([])
	const [year, setYear] = useState('')
	const [events, setEvents] = useState([])
	const [gp, setGp] = useState('')
	const [loadingYears, setLoadingYears] = useState(true)
	const [loadingEvents, setLoadingEvents] = useState(false)

	// Load years
	useEffect(() => {
		fetch(`${API_BASE}/years`)
			.then(r => r.json())
			.then(d => {
				const yrs = d.years || []
				setYears(yrs)
				if (yrs.length) setYear(yrs[yrs.length - 1])
			})
			.catch(() => {})
			.finally(() => setLoadingYears(false))
	}, [])

	// Load events when year changes
	useEffect(() => {
		if (!year) return
		setGp('')
		setLoadingEvents(true)
		fetch(`${API_BASE}/schedule?year=${year}`)
			.then(r => r.json())
			.then(d => {
				const evts = d.events || []
				setEvents(evts)
				if (evts.length) setGp(evts[0])
			})
			.catch(() => setEvents([]))
			.finally(() => setLoadingEvents(false))
	}, [year])

	const canPredict = year && gp

	const handlePredict = () => {
		if (canPredict) navigate(`/results/${year}/${encodeURIComponent(gp)}`)
	}

	const yearOpts  = years.map(y => ({ value: y, label: String(y) }))
	const eventOpts = events.map(e => ({ value: e, label: e }))

	return (
		<div className="relative min-h-screen flex flex-col overflow-hidden" style={{ background: '#0a0e17' }}>
			{/* Scanlines overlay */}
			<div className="scanlines" />

			{/* Background radial glows */}
			<div className="pointer-events-none absolute inset-0 z-0">
				<div style={{
					position: 'absolute', top: '-20%', right: '-10%',
					width: '70vw', height: '70vw', maxWidth: 900,
					background: 'radial-gradient(ellipse, rgba(232,0,45,0.08) 0%, transparent 65%)',
					borderRadius: '50%'
				}} />
				<div style={{
					position: 'absolute', bottom: '-10%', left: '-15%',
					width: '60vw', height: '60vw', maxWidth: 800,
					background: 'radial-gradient(ellipse, rgba(54,113,198,0.07) 0%, transparent 65%)',
					borderRadius: '50%'
				}} />
			</div>

			{/* Minimal top bar */}
			<header className="relative z-10 flex items-center justify-between px-6 py-4 border-b border-[#1e2a3a]">
				<div className="flex items-center gap-3">
					<div style={{ width: 4, height: 28, background: '#E8002D', borderRadius: 2 }} />
					<span className="font-display font-bold text-lg tracking-widest uppercase text-white" style={{ letterSpacing: '0.2em' }}>
						F1 Predictor
					</span>
				</div>
				<div className="font-mono text-xs text-[#3d4f66] tracking-widest uppercase">
					ML · FastF1 · 2018–2025
				</div>
			</header>

			{/* Hero */}
			<main className="relative z-10 flex flex-col items-center justify-center flex-1 px-4 py-16 md:py-24">

				{/* Eyebrow */}
				<div className="font-mono text-xs tracking-[0.3em] text-[#E8002D] uppercase mb-5 flex items-center gap-2">
					<Zap size={10} fill="currentColor" />
					Grand Prix Winner Prediction
					<Zap size={10} fill="currentColor" />
				</div>

				{/* Title */}
				<h1 className="font-display font-bold text-center leading-none mb-3 text-white"
					style={{ fontSize: 'clamp(3rem, 10vw, 7.5rem)', letterSpacing: '-0.01em', textTransform: 'uppercase' }}>
					Who Wins
					<br />
					<span style={{ color: '#E8002D' }}>The Race?</span>
				</h1>

				{/* Sub */}
				<p className="font-mono text-sm text-[#8899aa] text-center max-w-md mb-14 leading-relaxed">
					Gradient Boosting + Logistic Regression trained on{' '}
					<span className="text-white">7 seasons</span> of qualifying, grid, and historical data.
				</p>

				{/* Selector card */}
				<div className="w-full max-w-md panel-bright p-6 relative">
					{/* Red top stripe */}
					<div className="f1-stripe absolute top-0 left-0 right-0 rounded-t-lg" />

					<div className="telem-label mb-5">// SELECT RACE</div>

					<div className="grid grid-cols-2 gap-4 mb-4">
						<div>
							<div className="telem-label mb-2">SEASON</div>
							<Select
								value={year}
								onChange={setYear}
								options={yearOpts}
								placeholder={loadingYears ? 'Loading…' : 'Year'}
								disabled={loadingYears}
							/>
						</div>
						<div>
							<div className="telem-label mb-2">GRAND PRIX</div>
							<Select
								value={gp}
								onChange={setGp}
								options={eventOpts}
								placeholder={loadingEvents ? 'Loading…' : (year ? 'Select GP' : '—')}
								disabled={!year || loadingEvents}
							/>
						</div>
					</div>

					<button
						onClick={handlePredict}
						disabled={!canPredict}
						className="w-full font-display font-bold uppercase tracking-widest py-3 rounded-md transition-all duration-200"
						style={{
							fontSize: '1rem',
							letterSpacing: '0.2em',
							background: canPredict ? '#E8002D' : 'rgba(232,0,45,0.15)',
							color: canPredict ? '#fff' : 'rgba(255,255,255,0.3)',
							cursor: canPredict ? 'pointer' : 'not-allowed',
							boxShadow: canPredict ? '0 0 30px rgba(232,0,45,0.35)' : 'none',
						}}
					>
						Predict Winner
					</button>
				</div>

				{/* Stats strip */}
				<div className="mt-16 grid grid-cols-3 gap-8 text-center">
					{[
						{ val: '7', unit: 'Seasons', sub: '2018–2025' },
						{ val: '2', unit: 'Models',  sub: 'LR · GBC' },
						{ val: '20+', unit: 'Features', sub: 'per driver' },
					].map(({ val, unit, sub }) => (
						<div key={unit}>
							<div className="font-display font-bold text-white" style={{ fontSize: '2.5rem' }}>{val}</div>
							<div className="font-display font-semibold text-[#E8002D] text-sm tracking-widest uppercase">{unit}</div>
							<div className="font-mono text-xs text-[#3d4f66] mt-1">{sub}</div>
						</div>
					))}
				</div>
			</main>
		</div>
	)
}
