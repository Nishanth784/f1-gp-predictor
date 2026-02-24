import { useEffect, useState } from 'react'
import {
	LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function Compare() {
	const [years, setYears] = useState([])
	const [gps, setGps] = useState([])
	const [sessions, setSessions] = useState(["Q","R"])
	const [year, setYear] = useState(2023)
	const [gp, setGp] = useState('')
	const [session, setSession] = useState('Q')
	const [rows, setRows] = useState([])
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState('')

	useEffect(() => {
		(async () => { try { const r = await fetch(`${API_BASE}/years`); const d = await r.json(); setYears(d.years||[]); if(!year && d.years?.length) setYear(d.years[d.years.length-1]) } catch {} })()
	}, [])

	useEffect(() => {
		(async () => {
			try {
				const url = new URL(`${API_BASE}/metadata`)
				url.searchParams.set('year', String(year))
				if(gp) url.searchParams.set('gp', gp)
				const r = await fetch(url)
				const d = await r.json()
				setGps(d.gps||[]); setSessions(d.sessions||["Q","R"])
				if(!gp && (d.gps?.length)) setGp(d.gps[0])
			} catch {}
		})()
	}, [year, gp])

	const fetchData = async () => {
		setLoading(true); setError('')
		try {
			const url = new URL(`${API_BASE}/compare`)
			url.searchParams.set('year', String(year))
			url.searchParams.set('gp', gp)
			url.searchParams.set('session_type', session)
			const res = await fetch(url)
			if (!res.ok) throw new Error(await res.text())
			const data = await res.json()
			setRows(data.rows || [])
		} catch (err) { setError(String(err)) } finally { setLoading(false) }
	}

	useEffect(() => { fetchData() }, [])

	return (
		<div>
			<h2 className="text-2xl font-bold text-primary mb-4">Comparison Dashboard</h2>
			<div className="card mb-4 grid grid-cols-1 md:grid-cols-4 gap-3">
				<label className="label">Year
					<select className="input" value={year} onChange={e=>setYear(e.target.value)}>{years.map(y=><option key={y} value={y}>{y}</option>)}</select>
				</label>
				<label className="label">Grand Prix
					<select className="input" value={gp} onChange={e=>setGp(e.target.value)}>{gps.map((g,i)=><option key={i} value={g}>{g}</option>)}</select>
				</label>
				<label className="label">Session
					<select className="input" value={session} onChange={e=>setSession(e.target.value)}>{sessions.map(s=><option key={s} value={s}>{s==='Q'?'Qualifying':'Race'}</option>)}</select>
				</label>
				<button className="btn" onClick={fetchData} disabled={loading || !gp}>{loading ? 'Loading...' : 'Refresh'}</button>
			</div>

			{error && <div className="card text-red-400 mb-4 whitespace-pre-wrap">{error}</div>}

			{rows.length === 0 ? (
				<div className="card text-neutral-300">No data yet. Try another GP or session and click Refresh.</div>
			) : (
				<>
					<div className="card mb-6 overflow-auto">
						<table className="w-full text-left text-sm">
							<thead className="text-neutral-400">
								<tr>
									<th>Driver</th>
									<th>Team</th>
									<th>Lap</th>
									<th>Actual (s)</th>
									<th>Predicted (s)</th>
									<th>|Error| (s)</th>
								</tr>
							</thead>
							<tbody>
								{rows.map((r, i) => (
									<tr key={i} className="border-t border-neutral-800">
										<td>{r.Driver ?? ''}</td>
										<td>{r.Team ?? ''}</td>
										<td>{r.LapNumber ?? ''}</td>
										<td>{Number(r.ActualLapTime).toFixed(3)}</td>
										<td>{Number(r.PredictedLapTime).toFixed(3)}</td>
										<td>{Math.abs(Number(r.PredictedLapTime) - Number(r.ActualLapTime)).toFixed(3)}</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>

					<div className="card">
						<div className="h-80">
							<ResponsiveContainer width="100%" height="100%">
								<LineChart data={rows}>
									<CartesianGrid strokeDasharray="3 3" stroke="#333" />
									<XAxis dataKey="LapNumber" stroke="#bbb" />
									<YAxis stroke="#bbb" />
									<Tooltip />
									<Legend />
									<Line type="monotone" dataKey="ActualLapTime" stroke="#999" name="Actual" dot={false} />
									<Line type="monotone" dataKey="PredictedLapTime" stroke="#e10600" name="Predicted" dot={false} />
								</LineChart>
							</ResponsiveContainer>
						</div>
					</div>
				</>
			)}
		</div>
	)
}
