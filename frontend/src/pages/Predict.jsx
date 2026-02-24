import { useEffect, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function Predict() {
	const [years, setYears] = useState([])
	const [gps, setGps] = useState([])
	const [sessions, setSessions] = useState(["Q","R"])
	const [drivers, setDrivers] = useState([])
	const [teams, setTeams] = useState([])
	const [tyres, setTyres] = useState(["SOFT","MEDIUM","HARD"])

	const [form, setForm] = useState({ year: 2023, gp: '', session_type: 'Q', driver: '', team: '', tyre: 'SOFT', air: '', humidity: '' })
	const [result, setResult] = useState(null)
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState('')

	// Load years
	useEffect(() => {
		(async () => {
			try { const r = await fetch(`${API_BASE}/years`); const d = await r.json(); setYears(d.years||[]); if(!form.year && d.years?.length) setForm(f=>({...f, year: d.years[d.years.length-1]})) } catch {}
		})()
	}, [])

	// Load GP list for year and session meta (drivers/teams) when year/gp changes
	useEffect(() => {
		(async () => {
			try {
				const url = new URL(`${API_BASE}/metadata`)
				url.searchParams.set('year', String(form.year||''))
				if(form.gp) url.searchParams.set('gp', form.gp)
				const r = await fetch(url)
				const d = await r.json()
				setGps(d.gps||[]); setSessions(d.sessions||["Q","R"]); setDrivers(d.drivers||[]); setTeams(d.teams||[]); setTyres(d.tyres||["SOFT","MEDIUM","HARD"])
				if(!form.gp && (d.gps?.length)) setForm(f=>({...f, gp: d.gps[0]}))
				if(!form.driver && (d.drivers?.length)) setForm(f=>({...f, driver: d.drivers[0]}))
				if(!form.team && (d.teams?.length)) setForm(f=>({...f, team: d.teams[0]}))
			} catch {}
		})()
	}, [form.year, form.gp])

	const update = (k) => (e) => setForm({ ...form, [k]: e.target.value })

	const onSubmit = async (e) => {
		e.preventDefault()
		setLoading(true)
		setError('')
		try {
			const payload = {
				year: Number(form.year), gp: form.gp, session_type: form.session_type,
				driver: form.driver, team: form.team || undefined, tyre: form.tyre || undefined,
				weather: { AirTemp: form.air?Number(form.air):undefined, Humidity: form.humidity?Number(form.humidity):undefined }
			}
			const res = await fetch(`${API_BASE}/predict`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
			if (!res.ok) throw new Error(await res.text())
			const data = await res.json()
			setResult(data)
		} catch (err) { setError(String(err)) } finally { setLoading(false) }
	}

	return (
		<div>
			<h2 className="text-2xl font-bold text-primary mb-4">Lap Time Prediction</h2>
			<form onSubmit={onSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4 card">
				<label className="label">Year
					<select className="input" value={form.year} onChange={update('year')}>{years.map(y=><option key={y} value={y}>{y}</option>)}</select>
				</label>
				<label className="label">Grand Prix
					<select className="input" value={form.gp} onChange={update('gp')}>{gps.map((g,i)=><option key={i} value={g}>{g}</option>)}</select>
				</label>
				<label className="label">Session
					<select className="input" value={form.session_type} onChange={update('session_type')}>{sessions.map(s=><option key={s} value={s}>{s==='Q'?'Qualifying':'Race'}</option>)}</select>
				</label>
				<label className="label">Driver
					<select className="input" value={form.driver} onChange={update('driver')}>{drivers.map(d=><option key={d} value={d}>{d}</option>)}</select>
				</label>
				<label className="label">Team
					<select className="input" value={form.team} onChange={update('team')}>{teams.map(t=><option key={t} value={t}>{t}</option>)}</select>
				</label>
				<label className="label">Tyre
					<select className="input" value={form.tyre} onChange={update('tyre')}>{tyres.map(t=><option key={t} value={t}>{t}</option>)}</select>
				</label>
				<label className="label">Air Temp (°C)<input className="input" value={form.air} onChange={update('air')} placeholder="optional" /></label>
				<label className="label">Humidity (%)<input className="input" value={form.humidity} onChange={update('humidity')} placeholder="optional" /></label>
				<button className="btn md:col-span-2" disabled={loading || !form.gp || !form.driver || !form.team}>{loading ? 'Predicting...' : 'Predict'}</button>
			</form>
			{error && <div className="card mt-4 text-red-400 whitespace-pre-wrap">{error}</div>}
			{result && (
				<div className="card mt-4">
					<div className="text-lg">Predicted Lap Time: <span className="text-primary font-semibold">{result.predicted_lap_time.toFixed(3)} s</span></div>
				</div>
			)}
		</div>
	)
}
