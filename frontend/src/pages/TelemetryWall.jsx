import { useState, useEffect, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { parseRouteParams } from '../utils/sanitizeParams'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, CartesianGrid,
} from 'recharts'
import StatusBanner from '../components/StatusBanner'
import { getTeamColour, getTyreColour, TYRE_COLOURS } from '../components/TeamColours'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8011'

function PanelBox({ title, badge, children }) {
  return (
    <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
      display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '6px 12px', borderBottom: '1px solid #1e2535', background: '#0a0d14',
        flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="font-mono text-xs tracking-widest uppercase" style={{ color: '#3d4f66' }}>{title}</span>
        {badge && <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>{badge}</span>}
      </div>
      <div style={{ flex: 1, padding: 12, minHeight: 0 }}>{children}</div>
    </div>
  )
}

const COMPOUND_ABBR = { SOFT: 'S', MEDIUM: 'M', HARD: 'H', INTERMEDIATE: 'I', WET: 'W', UNKNOWN: '?' }

function msToStr(ms) {
  if (!ms) return '--'
  const s = ms / 1000
  const m = Math.floor(s / 60)
  const sec = (s % 60).toFixed(3).padStart(6, '0')
  return m > 0 ? `${m}:${sec}` : `${(s).toFixed(3)}`
}

const SECTOR_COLOUR = { purple: '#CC00FF', green: '#00FF00', yellow: '#FFD700', grey: '#3d4f66' }

function SectorDot({ colour }) {
  return (
    <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
      background: SECTOR_COLOUR[colour] || '#3d4f66', marginRight: 1,
      boxShadow: colour === 'purple' ? '0 0 4px #CC00FF' : colour === 'green' ? '0 0 3px #00FF00' : 'none' }} />
  )
}

export default function TelemetryWall() {
  const rawParams = useParams()
  const { year, gp: gpDecoded } = parseRouteParams(rawParams)

  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [selected, setSelected] = useState('')
  const [session, setSession]   = useState('R')   // R | Q

  useEffect(() => {
    if (!year || !gpDecoded) return
    setLoading(true)
    setError(null)
    setData(null)
    fetch(`${API_BASE}/timing/${year}/${encodeURIComponent(gpDecoded)}?session_type=${session}`)
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
      .then(d => {
        setData(d)
        setLoading(false)
        const drivers = d?.drivers || []
        if (drivers.length && !selected) setSelected(drivers[0].driver)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [year, gpDecoded, session])

  // All laps for selected driver
  const driverLaps = useMemo(() => {
    if (!data || !selected) return []
    return (data.laps || [])
      .filter(l => l.driver === selected && l.lap_time_ms && l.is_accurate)
      .sort((a, b) => a.lap_number - b.lap_number)
  }, [data, selected])

  const drivers = data?.drivers || []
  const driverInfo = drivers.find(d => d.driver === selected) || drivers[0]
  const colour = driverInfo ? getTeamColour(driverInfo.team || '') : '#8899aa'

  // Best lap
  const bestLap = useMemo(() => {
    if (!driverLaps.length) return null
    return driverLaps.reduce((best, l) => (!best || l.lap_time_ms < best.lap_time_ms) ? l : best, null)
  }, [driverLaps])

  // Chart data: lap time in seconds
  const lapChartData = driverLaps.map(l => ({
    lap:  l.lap_number,
    time: l.lap_time_ms ? +(l.lap_time_ms / 1000).toFixed(3) : null,
    pit:  l.is_pit_lap,
    cmpd: l.compound,
  }))

  // Position chart (for race)
  const posChartData = driverLaps
    .filter(l => l.position != null)
    .map(l => ({ lap: l.lap_number, pos: l.position }))

  // Median lap time for chart y-axis centering
  const times = lapChartData.map(d => d.time).filter(Boolean).sort((a, b) => a - b)
  const median = times[Math.floor(times.length / 2)] || 90
  const yMin = Math.floor(median - 8)
  const yMax = Math.ceil(median + 8)

  const Skeleton = () => (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} style={{ height: 22, background: 'rgba(255,255,255,0.04)', borderRadius: 3,
          animation: 'pulse 1.5s ease-in-out infinite', animationDelay: `${i * 0.08}s` }} />
      ))}
    </div>
  )

  return (
    <div style={{ minHeight: '100vh', background: '#080c12', display: 'flex', flexDirection: 'column' }}>
      <StatusBanner year={year} gp={gpDecoded} />

      {/* Session + driver selector bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 10px',
        background: '#0a0d14', borderBottom: '1px solid #1e2535', flexWrap: 'wrap' }}>

        {/* Session toggle */}
        <div className="flex gap-1">
          {['R', 'Q'].map(s => (
            <button key={s} onClick={() => { setSession(s); setSelected('') }}
              className="font-mono text-xs px-3 py-1"
              style={{ borderRadius: 4, border: `1px solid ${session === s ? '#E8002D' : '#1e2535'}`,
                background: session === s ? 'rgba(232,0,45,0.12)' : 'transparent',
                color: session === s ? '#fff' : '#3d4f66', cursor: 'pointer' }}>
              {s === 'R' ? 'RACE' : 'QUALIFYING'}
            </button>
          ))}
        </div>

        <div style={{ width: 1, height: 16, background: '#1e2535' }} />

        {/* Driver chips */}
        <div className="flex gap-1 flex-wrap">
          {drivers.map(d => {
            const tc = getTeamColour(d.team || '')
            const active = d.driver === selected
            return (
              <button key={d.driver} onClick={() => setSelected(d.driver)}
                className="font-mono text-xs px-2 py-1"
                style={{ borderRadius: 4, border: `1px solid ${active ? tc : '#1e2535'}`,
                  background: active ? `${tc}22` : 'transparent',
                  color: active ? tc : '#3d4f66', cursor: 'pointer', transition: 'all 0.1s' }}>
                {d.driver}
              </button>
            )
          })}
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center flex-1">
          <div className="flex flex-col items-center gap-3">
            <div style={{ width: 28, height: 28, borderRadius: '50%', border: '2px solid #E8002D',
              borderTopColor: 'transparent', animation: 'spin 0.8s linear infinite' }} />
            <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>LOADING SESSION DATA…</span>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-center justify-center flex-1">
          <span className="font-mono text-xs" style={{ color: '#E8002D' }}>
            Failed to load — session may not have data yet ({error})
          </span>
        </div>
      )}

      {!loading && !error && data && (
        <div style={{ flex: 1, display: 'grid', padding: 10, gap: 8,
          gridTemplateColumns: '1fr 1fr', gridTemplateRows: 'auto auto' }}>

          {/* LAP TIME PROGRESSION */}
          <PanelBox title={`LAP TIMES — ${selected}`}
            badge={bestLap ? `BEST ${msToStr(bestLap.lap_time_ms)} L${bestLap.lap_number}` : ''}>
            {driverLaps.length === 0 ? (
              <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>NO DATA</span>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={lapChartData} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
                  <CartesianGrid stroke="#1e2535" strokeDasharray="3 6" />
                  <XAxis dataKey="lap" tick={{ fontFamily: 'monospace', fontSize: 8, fill: '#3d4f66' }}
                    axisLine={false} tickLine={false} label={{ value: 'LAP', position: 'insideBottomRight',
                      offset: -4, style: { fontFamily: 'monospace', fontSize: 7, fill: '#3d4f66' } }} />
                  <YAxis domain={[yMin, yMax]}
                    tickFormatter={v => `${v}s`}
                    tick={{ fontFamily: 'monospace', fontSize: 8, fill: '#3d4f66' }}
                    axisLine={false} tickLine={false} width={34} />
                  <Tooltip
                    contentStyle={{ background: '#0d1018', border: '1px solid #1e2535',
                      fontFamily: 'monospace', fontSize: 10 }}
                    formatter={(v, n, props) => {
                      const raw = props?.payload
                      return [`${v}s${raw?.pit ? ' 🔴 PIT' : ''}`, 'Lap Time']
                    }}
                    labelFormatter={l => `Lap ${l}`}
                  />
                  {bestLap && (
                    <ReferenceLine y={bestLap.lap_time_ms / 1000}
                      stroke="#CC00FF" strokeDasharray="4 4" strokeWidth={1.5}
                      label={{ value: 'BEST', position: 'right',
                        style: { fontFamily: 'monospace', fontSize: 8, fill: '#CC00FF' } }} />
                  )}
                  <Line type="monotone" dataKey="time" stroke={colour} strokeWidth={2}
                    dot={(props) => {
                      const { cx, cy, payload } = props
                      if (payload.pit) return <circle key={cx} cx={cx} cy={cy} r={4} fill="#E8002D" stroke="none" />
                      if (bestLap && payload.lap === bestLap.lap_number)
                        return <circle key={cx} cx={cx} cy={cy} r={5} fill="#CC00FF" stroke="none" />
                      return <circle key={cx} cx={cx} cy={cy} r={2} fill={colour} stroke="none" />
                    }}
                    connectNulls={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
            <div className="flex gap-3 mt-2 flex-wrap">
              {[['●', colour, 'Lap'], ['●', '#E8002D', 'Pit Stop'], ['●', '#CC00FF', 'Best Lap']].map(([sym, c, lbl]) => (
                <span key={lbl} className="font-mono text-xs flex items-center gap-1" style={{ color: '#3d4f66' }}>
                  <span style={{ color: c }}>{sym}</span>{lbl}
                </span>
              ))}
            </div>
          </PanelBox>

          {/* POSITION CHART (Race only) */}
          {session === 'R' ? (
            <PanelBox title={`POSITION — ${selected}`}>
              {posChartData.length === 0 ? (
                <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>NO POSITION DATA</span>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={posChartData} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
                    <CartesianGrid stroke="#1e2535" strokeDasharray="3 6" />
                    <XAxis dataKey="lap" tick={{ fontFamily: 'monospace', fontSize: 8, fill: '#3d4f66' }}
                      axisLine={false} tickLine={false} />
                    <YAxis domain={[20, 1]} reversed
                      ticks={[1, 5, 10, 15, 20]}
                      tick={{ fontFamily: 'monospace', fontSize: 8, fill: '#3d4f66' }}
                      axisLine={false} tickLine={false} width={20}
                      tickFormatter={v => `P${v}`} />
                    <Tooltip contentStyle={{ background: '#0d1018', border: '1px solid #1e2535',
                      fontFamily: 'monospace', fontSize: 10 }}
                      formatter={v => [`P${v}`, 'Position']} labelFormatter={l => `Lap ${l}`} />
                    <Line type="monotone" dataKey="pos" stroke={colour} strokeWidth={2}
                      dot={false} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </PanelBox>
          ) : (
            /* Qualifying: show all laps table */
            <PanelBox title="QUALIFYING LAPS">
              <div style={{ overflowY: 'auto', maxHeight: 250 }}>
                {driverLaps.map((l, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8,
                    padding: '5px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <span className="font-mono text-xs" style={{ color: '#3d4f66', width: 16 }}>Q{l.lap_number}</span>
                    <span className="font-mono text-xs font-bold"
                      style={{ color: bestLap && l.lap_number === bestLap.lap_number ? '#CC00FF' : colour, width: 70 }}>
                      {msToStr(l.lap_time_ms)}
                    </span>
                    <SectorDot colour={l.s1_colour} />
                    <span className="font-mono" style={{ fontSize: 9, color: SECTOR_COLOUR[l.s1_colour], width: 52 }}>
                      S1 {msToStr(l.sector1_ms)}
                    </span>
                    <SectorDot colour={l.s2_colour} />
                    <span className="font-mono" style={{ fontSize: 9, color: SECTOR_COLOUR[l.s2_colour], width: 52 }}>
                      S2 {msToStr(l.sector2_ms)}
                    </span>
                    <SectorDot colour={l.s3_colour} />
                    <span className="font-mono" style={{ fontSize: 9, color: SECTOR_COLOUR[l.s3_colour], width: 52 }}>
                      S3 {msToStr(l.sector3_ms)}
                    </span>
                  </div>
                ))}
              </div>
            </PanelBox>
          )}

          {/* SECTOR BREAKDOWN TABLE */}
          <PanelBox title="SECTOR BREAKDOWN" badge="PURPLE=SESSION BEST  GREEN=PERSONAL BEST">
            <div style={{ overflowY: 'auto', maxHeight: 280 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '32px 72px 60px 60px 60px 32px 36px',
                gap: '0 6px', marginBottom: 6 }}>
                {['LAP', 'TIME', 'S1', 'S2', 'S3', 'CPD', 'POS'].map(h => (
                  <span key={h} className="font-mono" style={{ fontSize: 8, color: '#3d4f66' }}>{h}</span>
                ))}
              </div>
              {driverLaps.map((l, i) => (
                <div key={i} style={{ display: 'grid',
                  gridTemplateColumns: '32px 72px 60px 60px 60px 32px 36px',
                  gap: '0 6px', padding: '3px 0',
                  borderBottom: '1px solid rgba(255,255,255,0.03)',
                  background: bestLap && l.lap_number === bestLap.lap_number
                    ? 'rgba(204,0,255,0.06)' : l.is_pit_lap ? 'rgba(232,0,45,0.05)' : 'transparent' }}>
                  <span className="font-mono" style={{ fontSize: 9, color: '#3d4f66' }}>{l.lap_number}</span>
                  <span className="font-mono font-bold" style={{ fontSize: 9,
                    color: bestLap && l.lap_number === bestLap.lap_number ? '#CC00FF' : colour }}>
                    {msToStr(l.lap_time_ms)}
                  </span>
                  <span className="font-mono" style={{ fontSize: 9, color: SECTOR_COLOUR[l.s1_colour] }}>
                    {msToStr(l.sector1_ms)}
                  </span>
                  <span className="font-mono" style={{ fontSize: 9, color: SECTOR_COLOUR[l.s2_colour] }}>
                    {msToStr(l.sector2_ms)}
                  </span>
                  <span className="font-mono" style={{ fontSize: 9, color: SECTOR_COLOUR[l.s3_colour] }}>
                    {msToStr(l.sector3_ms)}
                  </span>
                  <span className="font-mono font-bold" style={{ fontSize: 9,
                    color: getTyreColour(l.compound) }}>
                    {COMPOUND_ABBR[l.compound] || '?'}
                  </span>
                  <span className="font-mono" style={{ fontSize: 9, color: '#8899aa' }}>
                    {l.position ? `P${l.position}` : '--'}
                  </span>
                </div>
              ))}
            </div>
          </PanelBox>

          {/* DRIVER COMPARISON TABLE */}
          <PanelBox title="BEST LAP — ALL DRIVERS">
            <div style={{ overflowY: 'auto', maxHeight: 280 }}>
              {(() => {
                const bestByDriver = {}
                for (const l of (data.laps || [])) {
                  if (!l.lap_time_ms || !l.is_accurate) continue
                  if (!bestByDriver[l.driver] || l.lap_time_ms < bestByDriver[l.driver].lap_time_ms)
                    bestByDriver[l.driver] = l
                }
                const rows = Object.values(bestByDriver).sort((a, b) => a.lap_time_ms - b.lap_time_ms)
                const pole = rows[0]?.lap_time_ms
                return rows.map((l, i) => {
                  const tc = getTeamColour(l.team || '')
                  const gap = pole ? (l.lap_time_ms - pole) / 1000 : 0
                  return (
                    <div key={l.driver} style={{ display: 'flex', alignItems: 'center', gap: 8,
                      padding: '5px 8px', borderBottom: '1px solid rgba(255,255,255,0.03)',
                      background: l.driver === selected ? `${tc}11` : 'transparent',
                      cursor: 'pointer' }}
                      onClick={() => setSelected(l.driver)}>
                      <span className="font-mono text-xs" style={{ color: '#3d4f66', width: 20 }}>P{i+1}</span>
                      <div style={{ width: 3, height: 14, background: tc, borderRadius: 1, flexShrink: 0 }} />
                      <span className="font-mono text-xs font-bold" style={{ color: tc, width: 30 }}>
                        {l.driver}
                      </span>
                      <span className="font-mono text-xs" style={{ color: i === 0 ? '#CC00FF' : '#8899aa', width: 68 }}>
                        {msToStr(l.lap_time_ms)}
                      </span>
                      <span className="font-mono text-xs" style={{ color: '#3d4f66', flex: 1 }}>
                        {i === 0 ? 'BEST' : `+${gap.toFixed(3)}s`}
                      </span>
                      <span className="font-mono font-bold" style={{ fontSize: 9,
                        color: getTyreColour(l.compound) }}>
                        {COMPOUND_ABBR[l.compound] || '?'}
                      </span>
                      <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>L{l.lap_number}</span>
                    </div>
                  )
                })
              })()}
            </div>
          </PanelBox>

        </div>
      )}

      {!loading && !error && !data && (
        <div className="flex items-center justify-center flex-1">
          <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>SELECT A RACE TO VIEW LAP DATA</span>
        </div>
      )}

      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}
