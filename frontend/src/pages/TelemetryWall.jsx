import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { parseRouteParams } from '../utils/sanitizeParams'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, Cell
} from 'recharts'
import StatusBanner from '../components/StatusBanner'
import { getTeamColour } from '../components/TeamColours'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8011'

function PanelBox({ title, children }) {
  return (
    <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
      display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '6px 12px', borderBottom: '1px solid #1e2535', background: '#0a0d14',
        flexShrink: 0 }}>
        <span className="font-mono text-xs tracking-widest uppercase" style={{ color: '#3d4f66' }}>
          {title}
        </span>
      </div>
      <div style={{ flex: 1, padding: 12, minHeight: 0 }}>{children}</div>
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 4, padding: '8px 12px' }}>
      <div className="font-mono text-xs font-bold text-white mb-1">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="font-mono text-xs" style={{ color: p.color || '#8899aa' }}>
          {p.name}: {typeof p.value === 'number' ? (p.value * 100).toFixed(1) + '%' : p.value}
        </div>
      ))}
    </div>
  )
}

export default function TelemetryWall() {
  const rawParams = useParams()
  const { year, gp: gpDecoded } = parseRouteParams(rawParams)

  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!year || !gpDecoded) return
    setLoading(true)
    fetch(`${API_BASE}/winner-probabilities?year=${year}&gp=${encodeURIComponent(gpDecoded)}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [year, gpDecoded])

  const drivers  = data?.predictions || []
  const top10    = drivers.slice(0, 10)
  const chaos    = data?.chaos_index ?? 0
  const scRate   = data?.sc_rate ?? 0

  // Chart 1: Win probability comparison (top 10)
  const probData = top10.map(d => ({
    name: (d.driver || d.Driver || '').slice(0, 3).toUpperCase(),
    likely: d.likely_probability ?? d.probability ?? 0,
    best:   d.scenarios?.best_case ?? 0,
    worst:  d.scenarios?.worst_case ?? 0,
    colour: getTeamColour(d.team || d.Team || ''),
  }))

  // Chart 2: Scenario spread (best-worst gap, sorted by spread width)
  const spreadData = [...probData]
    .map(d => ({ ...d, spread: (d.best - d.worst) * 100 }))
    .sort((a, b) => b.spread - a.spread)
    .slice(0, 8)

  // Chart 3: Chaos breakdown radar
  const gridSpread = Math.min(1, chaos * 1.2)
  const windFactor = Math.min(1, chaos * 0.8)
  const radarData = [
    { metric: 'SC Rate',     value: scRate * 100 },
    { metric: 'Grid Spread', value: gridSpread * 100 },
    { metric: 'Wind',        value: windFactor * 100 },
    { metric: 'Chaos Index', value: chaos * 100 },
    { metric: 'Variance',    value: spreadData[0]?.spread ?? 0 },
  ]

  // Chart 4: Top 5 probability comparison bars (best/likely/worst grouped)
  const scenarioData = drivers.slice(0, 5).map(d => ({
    name: (d.driver || d.Driver || '').slice(0, 3).toUpperCase(),
    Best:   +((d.scenarios?.best_case ?? 0) * 100).toFixed(1),
    Likely: +((d.likely_probability ?? 0) * 100).toFixed(1),
    Worst:  +((d.scenarios?.worst_case ?? 0) * 100).toFixed(1),
  }))

  const Skeleton = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} style={{ height: 24, background: 'rgba(255,255,255,0.04)', borderRadius: 3,
          animation: 'pulse 1.5s ease-in-out infinite', animationDelay: `${i * 0.1}s` }} />
      ))}
    </div>
  )

  return (
    <div style={{ minHeight: '100vh', background: '#080c12', display: 'flex', flexDirection: 'column' }}>
      <StatusBanner year={year} gp={gpDecoded} />
      <div style={{ flex: 1, display: 'grid', padding: 10, gap: 8,
        gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr' }}>

        {/* Chart 1: Win probability */}
        <PanelBox title="WIN PROBABILITY — TOP 10">
          {loading ? <Skeleton /> : (
            <ResponsiveContainer width="100%" height="100%" minHeight={200}>
              <BarChart data={probData} margin={{ top: 4, right: 8, bottom: 4, left: -20 }}>
                <XAxis dataKey="name" tick={{ fontFamily: 'monospace', fontSize: 9, fill: '#3d4f66' }}
                  axisLine={false} tickLine={false} />
                <YAxis tickFormatter={v => `${(v*100).toFixed(0)}%`}
                  tick={{ fontFamily: 'monospace', fontSize: 9, fill: '#3d4f66' }}
                  axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="likely" radius={[3,3,0,0]} name="Win Probability">
                  {probData.map((d, i) => <Cell key={i} fill={d.colour} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </PanelBox>

        {/* Chart 2: Scenario ranges (best vs worst) */}
        <PanelBox title="SCENARIO SPREAD — BEST vs WORST">
          {loading ? <Skeleton /> : (
            <ResponsiveContainer width="100%" height="100%" minHeight={200}>
              <BarChart data={scenarioData} margin={{ top: 4, right: 8, bottom: 4, left: -20 }}>
                <XAxis dataKey="name" tick={{ fontFamily: 'monospace', fontSize: 9, fill: '#3d4f66' }}
                  axisLine={false} tickLine={false} />
                <YAxis tickFormatter={v => `${v}%`}
                  tick={{ fontFamily: 'monospace', fontSize: 9, fill: '#3d4f66' }}
                  axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: '#0d1018', border: '1px solid #1e2535',
                  fontFamily: 'monospace', fontSize: 10 }} />
                <Legend wrapperStyle={{ fontFamily: 'monospace', fontSize: 9, color: '#3d4f66' }} />
                <Bar dataKey="Best"   fill="#00ff8866" radius={[3,3,0,0]} />
                <Bar dataKey="Likely" fill="#E8002D"   radius={[3,3,0,0]} />
                <Bar dataKey="Worst"  fill="#3d4f6688" radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </PanelBox>

        {/* Chart 3: Chaos radar */}
        <PanelBox title="CHAOS BREAKDOWN — RADAR">
          {loading ? <Skeleton /> : (
            <ResponsiveContainer width="100%" height="100%" minHeight={200}>
              <RadarChart data={radarData} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
                <PolarGrid stroke="#1e2535" />
                <PolarAngleAxis dataKey="metric"
                  tick={{ fontFamily: 'monospace', fontSize: 8, fill: '#3d4f66' }} />
                <Radar dataKey="value" stroke="#E8002D" fill="#E8002D" fillOpacity={0.15}
                  strokeWidth={2} dot={{ r: 3, fill: '#E8002D' }} />
              </RadarChart>
            </ResponsiveContainer>
          )}
        </PanelBox>

        {/* Chart 4: Probability uncertainty spread */}
        <PanelBox title="UNCERTAINTY SPREAD — TOP 8 DRIVERS">
          {loading ? <Skeleton /> : (
            <ResponsiveContainer width="100%" height="100%" minHeight={200}>
              <BarChart data={spreadData} layout="vertical"
                margin={{ top: 4, right: 32, bottom: 4, left: 4 }}>
                <XAxis type="number" tickFormatter={v => `${v.toFixed(0)}%`}
                  tick={{ fontFamily: 'monospace', fontSize: 9, fill: '#3d4f66' }}
                  axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" width={28}
                  tick={{ fontFamily: 'monospace', fontSize: 9, fill: '#3d4f66' }}
                  axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: '#0d1018', border: '1px solid #1e2535',
                  fontFamily: 'monospace', fontSize: 10 }}
                  formatter={v => [`${v.toFixed(1)}pp range`, 'Uncertainty']} />
                <Bar dataKey="spread" radius={[0,3,3,0]} name="Uncertainty">
                  {spreadData.map((d, i) => <Cell key={i} fill={d.colour} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </PanelBox>
      </div>
    </div>
  )
}
