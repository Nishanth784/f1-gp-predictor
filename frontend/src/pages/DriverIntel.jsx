import { useState, useEffect, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { User, TrendingUp, Target, Award, Flag } from 'lucide-react'
import StatusBanner from '../components/StatusBanner'
import { getTeamColour } from '../components/TeamColours'
import { parseRouteParams } from '../utils/sanitizeParams'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8011'

function PanelBox({ title, children, accent }) {
  return (
    <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      borderLeft: accent ? `3px solid ${accent}` : undefined }}>
      <div style={{ padding: '6px 12px', borderBottom: '1px solid #1e2535', background: '#0a0d14', flexShrink: 0 }}>
        <span className="font-mono text-xs tracking-widest uppercase" style={{ color: '#3d4f66' }}>{title}</span>
      </div>
      <div style={{ flex: 1, padding: 12, minHeight: 0 }}>{children}</div>
    </div>
  )
}

function StatCard({ label, value, sub, colour = '#8899aa' }) {
  return (
    <div style={{ background: '#0a0d14', border: '1px solid #1e2535', borderRadius: 5, padding: '8px 12px' }}>
      <div className="font-mono text-xs tracking-widest uppercase mb-1" style={{ color: '#3d4f66' }}>{label}</div>
      <div className="font-mono font-bold" style={{ fontSize: 18, color: colour }}>{value}</div>
      {sub && <div className="font-mono text-xs mt-1" style={{ color: '#3d4f66' }}>{sub}</div>}
    </div>
  )
}

const POS_COLOURS = { 1: '#FFD700', 2: '#C0C0C0', 3: '#CD7F32' }
function posColour(p) {
  if (!p) return '#3d4f66'
  if (p <= 3) return POS_COLOURS[p]
  if (p <= 5) return '#00ff88'
  if (p <= 10) return '#8899aa'
  return '#3d4f66'
}

// Past season results — we derive from multiple GP timing calls
// For simplicity, show from the predictions: driver_avg_position + win_rate as proxy
// Plus show all drivers ranked by probability for context

export default function DriverIntel() {
  const rawParams = useParams()
  const { year, gp: gpDecoded } = parseRouteParams(rawParams)

  const [data, setData]         = useState(null)
  const [loading, setLoading]   = useState(false)
  const [selected, setSelected] = useState('')

  // Load current GP predictions (has win rate, avg position, grid position etc)
  useEffect(() => {
    if (!year || !gpDecoded) return
    setLoading(true)
    fetch(`${API_BASE}/winner-probabilities?year=${year}&gp=${encodeURIComponent(gpDecoded)}`)
      .then(r => r.json())
      .then(d => {
        setData(d)
        setLoading(false)
        const preds = d?.predictions || []
        if (preds.length && !selected) setSelected(preds[0].driver || preds[0].Driver || '')
      })
      .catch(() => setLoading(false))
  }, [year, gpDecoded])

  // Load schedule to get previous races this season for form chart
  const [schedule, setSchedule]       = useState([])
  const [formData, setFormData]       = useState({})   // { gpName: position }
  const [formLoading, setFormLoading] = useState(false)

  useEffect(() => {
    if (!year) return
    fetch(`${API_BASE}/schedule?year=${year}`)
      .then(r => r.json())
      .then(d => setSchedule(d?.schedule || []))
      .catch(() => {})
  }, [year])

  useEffect(() => {
    if (!selected || !schedule.length || !year) return
    // Find past races (before current GP, already happened)
    const currentIdx = schedule.findIndex(s => s.EventName === gpDecoded || s.EventName?.includes(gpDecoded?.replace(' Grand Prix','').trim()))
    const past = schedule.slice(0, currentIdx > 0 ? currentIdx : schedule.length).slice(-6)
    if (!past.length) return

    setFormLoading(true)
    const driverCode = selected.slice(0, 3).toUpperCase()

    Promise.allSettled(
      past.map(gp =>
        fetch(`${API_BASE}/timing/${year}/${encodeURIComponent(gp.EventName)}?session_type=R`)
          .then(r => r.ok ? r.json() : null)
          .then(d => {
            if (!d) return null
            // Find finish position: last lap entry for this driver
            const drvLaps = (d.laps || []).filter(l => l.driver === driverCode || l.driver === selected)
            if (!drvLaps.length) return null
            const lastLap = drvLaps.sort((a, b) => b.lap_number - a.lap_number)[0]
            return { gp: gp.EventName?.replace(' Grand Prix',''), position: lastLap?.position }
          })
          .catch(() => null)
      )
    ).then(results => {
      const out = {}
      past.forEach((gp, i) => {
        const r = results[i]
        if (r.status === 'fulfilled' && r.value) {
          out[r.value.gp || gp.EventName] = r.value.position
        }
      })
      setFormData(out)
      setFormLoading(false)
    })
  }, [selected, schedule, year])

  const drivers  = data?.predictions || []
  const driver   = drivers.find(d => (d.driver || d.Driver) === selected) || drivers[0]
  const colour   = driver ? getTeamColour(driver.team || driver.Team || '') : '#8899aa'

  const likely  = driver?.likely_probability ?? driver?.probability ?? 0
  const best    = driver?.scenarios?.best_case ?? likely
  const worst   = driver?.scenarios?.worst_case ?? likely
  const gridPos = driver?.grid_position ?? driver?.GridPosition ?? null
  const qualiGap = driver?.qualifying_time_gap ?? driver?.QualiTimeGap ?? null
  const winRate  = driver?.driver_win_rate ?? driver?.DriverWinRate ?? null
  const avgPos   = driver?.driver_avg_position ?? driver?.DriverAvgPosition ?? null
  const team     = driver?.team || driver?.Team || ''
  const name     = driver?.driver || driver?.Driver || ''

  // Find teammate
  const teammate = drivers.find(d => {
    const dt = d.team || d.Team || ''
    const dn = d.driver || d.Driver || ''
    return dt === team && dn !== name
  })
  const tmColour = teammate ? getTeamColour(teammate.team || teammate.Team || '') : '#8899aa'
  const tmLikely = teammate?.likely_probability ?? teammate?.probability ?? 0
  const tmGrid   = teammate?.grid_position ?? teammate?.GridPosition ?? null
  const tmGap    = teammate?.qualifying_time_gap ?? teammate?.QualiTimeGap ?? null
  const tmAvg    = teammate?.driver_avg_position ?? teammate?.DriverAvgPosition ?? null

  // Season performance proxy from win_rate and avg_position
  // Derive rough wins/podiums estimate from win rate and number of races
  const currentIdx = schedule.findIndex(s => s.EventName === gpDecoded || s.EventName?.includes(gpDecoded?.replace(' Grand Prix','').trim()))
  const racesRun = currentIdx > 0 ? currentIdx : schedule.length
  const estWins    = winRate != null ? Math.round(winRate * racesRun) : null
  const estPodiums = avgPos != null && avgPos <= 5 ? Math.round(racesRun * 0.6) : null

  const formEntries = Object.entries(formData)

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#080c12', display: 'flex', flexDirection: 'column' }}>
        <StatusBanner year={year} gp={gpDecoded} />
        <div className="flex items-center justify-center flex-1">
          <div style={{ width: 24, height: 24, borderRadius: '50%', border: '2px solid #E8002D',
            borderTopColor: 'transparent', animation: 'spin 0.8s linear infinite' }} />
        </div>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', background: '#080c12', display: 'flex', flexDirection: 'column' }}>
      <StatusBanner year={year} gp={gpDecoded} />

      {/* Driver selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
        background: '#0a0d14', borderBottom: '1px solid #1e2535', flexWrap: 'wrap' }}>
        <User size={11} style={{ color: '#3d4f66' }} />
        <span className="font-mono text-xs tracking-widest" style={{ color: '#3d4f66' }}>SELECT DRIVER</span>
        <div className="flex gap-1 flex-wrap" style={{ marginLeft: 8 }}>
          {drivers.map((d) => {
            const dc = d.driver || d.Driver || ''
            const tc = getTeamColour(d.team || d.Team || '')
            const active = dc === selected
            return (
              <button key={dc} onClick={() => setSelected(dc)}
                className="font-mono text-xs px-2 py-1"
                style={{ borderRadius: 4, border: `1px solid ${active ? tc : '#1e2535'}`,
                  background: active ? `${tc}22` : 'transparent',
                  color: active ? tc : '#3d4f66', cursor: 'pointer', transition: 'all 0.1s' }}>
                {dc.slice(0, 3).toUpperCase()}
              </button>
            )
          })}
        </div>
      </div>

      <div style={{ flex: 1, display: 'grid', padding: 10, gap: 8,
        gridTemplateColumns: '240px 1fr 1fr', gridTemplateRows: 'auto auto' }}>

        {/* ── COLUMN 1: Identity + Quick Stats ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>

          {/* Identity card */}
          <PanelBox title="DRIVER" accent={colour}>
            <div className="font-mono text-xs tracking-widest mb-1" style={{ color: '#3d4f66' }}>
              {team.toUpperCase()}
            </div>
            <div className="font-mono font-bold text-white" style={{ fontSize: 32, letterSpacing: 4 }}>
              {name.slice(0, 3).toUpperCase()}
            </div>
            <div className="font-mono text-xs" style={{ color: colour }}>{name}</div>
            <div style={{ marginTop: 10, height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
              <div style={{ width: `${likely * 200}%`, maxWidth: '100%', height: '100%',
                background: colour, borderRadius: 2, boxShadow: `0 0 8px ${colour}66`,
                transition: 'width 0.8s ease-out' }} />
            </div>
            <div className="flex justify-between mt-2">
              <div>
                <div className="font-mono text-xs" style={{ color: '#3d4f66' }}>WIN PROB</div>
                <div className="font-mono font-bold" style={{ fontSize: 20, color: colour }}>
                  {(likely * 100).toFixed(1)}%
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="font-mono text-xs" style={{ color: '#3d4f66' }}>RANGE</div>
                <div className="font-mono text-xs" style={{ color: '#3d4f66' }}>
                  <span style={{ color: '#E8002D' }}>{(worst*100).toFixed(0)}%</span>
                  {' — '}
                  <span style={{ color: '#00ff88' }}>{(best*100).toFixed(0)}%</span>
                </div>
              </div>
            </div>
          </PanelBox>

          {/* Quick stats grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            <StatCard label="Grid"    value={gridPos != null ? `P${gridPos}` : '--'} colour={colour} />
            <StatCard label="Quali Δ" value={qualiGap != null ? `+${qualiGap.toFixed(3)}` : '--'}
              sub="to pole" colour="#FF8000" />
            <StatCard label="Avg Fin" value={avgPos != null ? `P${avgPos.toFixed(1)}` : '--'}
              sub={`${year} season`} colour="#27F4D2" />
            <StatCard label="Win Rate" value={winRate != null ? `${(winRate*100).toFixed(0)}%` : '--'}
              sub={`~${estWins ?? '?'} wins`} colour={colour} />
          </div>

          {/* Top predictions ranking */}
          <PanelBox title="FULL FIELD RANKING">
            <div style={{ overflowY: 'auto', maxHeight: 180 }}>
              {drivers.map((d, i) => {
                const dc = d.driver || d.Driver || ''
                const tc = getTeamColour(d.team || d.Team || '')
                const p  = d.likely_probability ?? d.probability ?? 0
                const isMe = dc === selected
                return (
                  <div key={dc} onClick={() => setSelected(dc)}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0',
                      borderBottom: '1px solid rgba(255,255,255,0.03)',
                      background: isMe ? `${tc}11` : 'transparent',
                      cursor: 'pointer' }}>
                    <span className="font-mono text-xs" style={{ color: '#3d4f66', width: 20 }}>P{i+1}</span>
                    <div style={{ width: 3, height: 12, background: tc, borderRadius: 1 }} />
                    <span className="font-mono text-xs font-bold" style={{ color: isMe ? tc : '#8899aa', width: 28 }}>
                      {dc.slice(0,3).toUpperCase()}
                    </span>
                    <div style={{ flex: 1, height: 3, background: 'rgba(255,255,255,0.05)', borderRadius: 2 }}>
                      <div style={{ width: `${p * 400}%`, maxWidth: '100%', height: '100%',
                        background: tc, borderRadius: 2 }} />
                    </div>
                    <span className="font-mono text-xs" style={{ color: tc, width: 36, textAlign: 'right' }}>
                      {(p*100).toFixed(1)}%
                    </span>
                  </div>
                )
              })}
            </div>
          </PanelBox>
        </div>

        {/* ── COLUMN 2: Recent Form + Circuit History ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>

          {/* Recent form */}
          <PanelBox title={`RECENT FORM — ${name.slice(0,3).toUpperCase()} (LAST ${formEntries.length || '…'} RACES)`}>
            {formLoading ? (
              <div className="flex items-center gap-2">
                <div style={{ width: 14, height: 14, borderRadius: '50%', border: '2px solid #E8002D',
                  borderTopColor: 'transparent', animation: 'spin 0.8s linear infinite' }} />
                <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>LOADING RESULTS…</span>
              </div>
            ) : formEntries.length === 0 ? (
              <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>
                {schedule.length === 0 ? 'LOADING SCHEDULE…' : 'NO PREVIOUS RACE DATA FOR THIS SEASON YET'}
              </span>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {formEntries.map(([gpName, pos]) => {
                  const pc = posColour(pos)
                  return (
                    <div key={gpName} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="font-mono text-xs" style={{ color: '#3d4f66', minWidth: 90 }}>
                        {gpName || '—'}
                      </span>
                      <div style={{ flex: 1, height: 14, background: 'rgba(255,255,255,0.04)',
                        borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{ width: `${Math.max(5, (21-(pos||20))/20 * 100)}%`, height: '100%',
                          background: pc, borderRadius: 3, opacity: 0.8 }} />
                      </div>
                      <span className="font-mono font-bold text-xs" style={{ color: pc, width: 28, textAlign: 'right' }}>
                        {pos ? `P${pos}` : 'DNF'}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </PanelBox>

          {/* Season context: how driver ranks vs field on key metrics */}
          <PanelBox title="SEASON METRICS vs FIELD">
            {(() => {
              const metrics = [
                { label: 'Win Probability',   val: likely,  fmt: v => `${(v*100).toFixed(1)}%`, max: Math.max(...drivers.map(d => d.likely_probability ?? d.probability ?? 0)) },
                { label: 'Avg Finish',        val: avgPos != null ? 21 - avgPos : null,  fmt: () => avgPos != null ? `P${avgPos.toFixed(1)}` : '--', max: 20 },
                { label: 'Grid Position',     val: gridPos != null ? 21 - gridPos : null, fmt: () => gridPos != null ? `P${gridPos}` : '--', max: 20 },
                { label: 'Win Rate',          val: winRate, fmt: v => `${(v*100).toFixed(0)}%`, max: Math.max(...drivers.map(d => d.driver_win_rate ?? 0)) },
              ]
              return metrics.map(({ label, val, fmt, max }) => {
                const pct = (val != null && max > 0) ? Math.min(1, val / max) : 0
                // Rank among all drivers
                const rank = label === 'Win Probability'
                  ? drivers.findIndex(d => (d.driver || d.Driver) === name) + 1
                  : null
                return (
                  <div key={label} style={{ marginBottom: 10 }}>
                    <div className="flex justify-between mb-1">
                      <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>{label}</span>
                      <div className="flex gap-2 items-center">
                        {rank && <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>#{rank}</span>}
                        <span className="font-mono text-xs font-bold" style={{ color: colour }}>
                          {val != null ? fmt(val) : '--'}
                        </span>
                      </div>
                    </div>
                    <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                      <div style={{ width: `${pct * 100}%`, height: '100%', background: colour,
                        borderRadius: 2, boxShadow: `0 0 4px ${colour}55`, transition: 'width 0.6s ease-out' }} />
                    </div>
                  </div>
                )
              })
            })()}
          </PanelBox>
        </div>

        {/* ── COLUMN 3: Teammate H2H + Circuit History ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>

          {/* Teammate Head-to-Head */}
          <PanelBox title="HEAD-TO-HEAD — TEAMMATE">
            {!teammate ? (
              <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>TEAMMATE NOT FOUND IN PREDICTIONS</span>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-4">
                  {/* Me */}
                  <div style={{ textAlign: 'center', flex: 1 }}>
                    <div style={{ fontFamily: 'monospace', fontSize: 24, fontWeight: 700,
                      color: colour, letterSpacing: 4 }}>
                      {name.slice(0,3).toUpperCase()}
                    </div>
                    <div className="font-mono text-xs" style={{ color: '#3d4f66' }}>{team}</div>
                  </div>
                  <div style={{ fontFamily: 'monospace', fontSize: 11, color: '#3d4f66' }}>VS</div>
                  {/* Teammate */}
                  <div style={{ textAlign: 'center', flex: 1 }}>
                    <div style={{ fontFamily: 'monospace', fontSize: 24, fontWeight: 700,
                      color: tmColour, letterSpacing: 4 }}>
                      {(teammate.driver || teammate.Driver || '').slice(0,3).toUpperCase()}
                    </div>
                    <div className="font-mono text-xs" style={{ color: '#3d4f66' }}>{team}</div>
                  </div>
                </div>

                {/* Comparison rows */}
                {[
                  { label: 'Win Probability', myVal: `${(likely*100).toFixed(1)}%`,    tmVal: `${(tmLikely*100).toFixed(1)}%`,   myC: colour, tmC: tmColour, myNum: likely, tmNum: tmLikely },
                  { label: 'Grid Position',   myVal: gridPos ? `P${gridPos}` : '--',   tmVal: tmGrid  ? `P${tmGrid}` : '--',     myC: colour, tmC: tmColour, myNum: tmGrid  ? 21-gridPos : null, tmNum: gridPos ? 21-tmGrid  : null },
                  { label: 'Quali Gap',       myVal: qualiGap != null ? `+${qualiGap.toFixed(3)}s` : '--', tmVal: tmGap != null ? `+${tmGap.toFixed(3)}s` : '--', myC: colour, tmC: tmColour, myNum: tmGap != null ? -qualiGap : null, tmNum: qualiGap != null ? -tmGap : null },
                  { label: 'Avg Finish',      myVal: avgPos   ? `P${avgPos.toFixed(1)}`  : '--',  tmVal: tmAvg   ? `P${tmAvg.toFixed(1)}` : '--',   myC: colour, tmC: tmColour, myNum: tmAvg ? 21-avgPos : null,  tmNum: avgPos ? 21-tmAvg : null },
                ].map(({ label, myVal, tmVal, myC, tmC, myNum, tmNum }) => {
                  const edge = (myNum != null && tmNum != null) ? (myNum > tmNum ? 'me' : myNum < tmNum ? 'tm' : 'tie') : 'tie'
                  return (
                    <div key={label} style={{ marginBottom: 8 }}>
                      <div className="flex justify-between mb-1">
                        <span className="font-mono text-xs font-bold"
                          style={{ color: edge === 'me' ? myC : '#8899aa' }}>{myVal}</span>
                        <span className="font-mono text-xs" style={{ color: '#3d4f66', fontSize: 8 }}>{label}</span>
                        <span className="font-mono text-xs font-bold"
                          style={{ color: edge === 'tm' ? tmC : '#8899aa' }}>{tmVal}</span>
                      </div>
                      {/* Bar */}
                      <div style={{ height: 4, display: 'flex', borderRadius: 2, overflow: 'hidden', gap: 1 }}>
                        {myNum != null && tmNum != null ? (
                          <>
                            <div style={{ flex: myNum, background: myC, opacity: edge==='me' ? 1 : 0.4 }} />
                            <div style={{ flex: tmNum, background: tmC, opacity: edge==='tm' ? 1 : 0.4 }} />
                          </>
                        ) : (
                          <div style={{ flex: 1, background: 'rgba(255,255,255,0.06)' }} />
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </PanelBox>

          {/* Circuit history — best finishes across all available GPs at this circuit */}
          <PanelBox title={`CIRCUIT HISTORY — ${gpDecoded?.replace(' Grand Prix','') || ''}`}>
            <div style={{ marginBottom: 8 }}>
              <div className="font-mono text-xs" style={{ color: '#3d4f66', marginBottom: 6 }}>
                PAST RESULTS AT THIS CIRCUIT (from prediction model data)
              </div>
              <div className="flex gap-3 flex-wrap">
                <StatCard label="Best Prob" value={`${(best*100).toFixed(1)}%`}
                  sub="best case scenario" colour="#00ff88" />
                <StatCard label="Likely" value={`${(likely*100).toFixed(1)}%`}
                  sub="model prediction" colour={colour} />
              </div>
              <div style={{ marginTop: 10 }}>
                <div className="font-mono text-xs mb-2" style={{ color: '#3d4f66' }}>
                  CIRCUIT-SPECIFIC FACTORS
                </div>
                {[
                  { label: 'Grid Advantage', val: gridPos != null ? Math.max(0, 11 - gridPos) : 5, max: 10,
                    note: gridPos != null ? (gridPos <= 3 ? 'Top 3 start' : gridPos <= 6 ? 'Good start' : 'Midfield start') : '—' },
                  { label: 'Qualifying Pace', val: qualiGap != null ? Math.max(0, 3 - qualiGap) : 1.5, max: 3,
                    note: qualiGap != null ? (qualiGap < 0.1 ? 'Pole pace' : qualiGap < 0.3 ? 'Strong' : 'Gap to close') : '—' },
                  { label: 'Race Consistency', val: avgPos != null ? Math.max(0, 21 - avgPos) : 12, max: 20,
                    note: avgPos != null ? `${year} avg: P${avgPos.toFixed(1)}` : '—' },
                ].map(({ label, val, max, note }) => (
                  <div key={label} style={{ marginBottom: 8 }}>
                    <div className="flex justify-between mb-1">
                      <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>{label}</span>
                      <span className="font-mono text-xs" style={{ color: '#8899aa' }}>{note}</span>
                    </div>
                    <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                      <div style={{ width: `${Math.min(100, (val/max)*100)}%`, height: '100%',
                        background: colour, borderRadius: 2, transition: 'width 0.6s ease-out' }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </PanelBox>
        </div>

      </div>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}
