import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ChevronDown, RefreshCw, AlertTriangle } from 'lucide-react'
import StatusBanner from '../components/StatusBanner'
import LeaderBoard from '../components/LeaderBoard'
import CircuitMap from '../components/CircuitMap'
import ChaosDisplay from '../components/ChaosDisplay'
import { getTeamColour } from '../components/TeamColours'
import { sanitizeYear, sanitizeGP } from '../utils/sanitizeParams'

// Practice fastest-lap leaderboard
function PracticeLeaderboard({ drivers = [] }) {
  if (!drivers.length) return (
    <div className="flex items-center justify-center h-40">
      <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>AWAITING PRACTICE DATA</span>
    </div>
  )
  const best = drivers[0]?.fastest_lap_ms ?? 1
  return (
    <div style={{ overflowY: 'auto', maxHeight: '100%' }}>
      {drivers.map((d, i) => {
        const colour = (window.__getTeamColour?.(d.team) || '#8899aa')
        const gap = i === 0 ? '' : d.gap_ms != null ? `+${(d.gap_ms/1000).toFixed(3)}` : ''
        const lapStr = d.fastest_lap_ms
          ? (() => { const s=d.fastest_lap_ms/1000; const m=Math.floor(s/60); return `${m}:${(s%60).toFixed(3).padStart(6,'0')}`})()
          : '--'
        return (
          <div key={d.driver} style={{ display:'flex', alignItems:'center', gap:8, padding:'7px 12px',
            borderBottom:'1px solid rgba(255,255,255,0.04)',
            background: i===0 ? 'rgba(255,215,0,0.04)' : 'transparent' }}>
            <span style={{ fontFamily:'monospace', fontSize:9, color: i<3 ? ['#FFD700','#C0C0C0','#CD7F32'][i] : '#3d4f66', width:20 }}>
              P{i+1}
            </span>
            <div style={{ width:8, height:8, borderRadius:'50%', background: colour, flexShrink:0,
              boxShadow:`0 0 6px ${colour}88` }} />
            <span style={{ fontFamily:'monospace', fontSize:11, fontWeight:700, color:'#fff', width:30 }}>
              {d.driver?.slice(0,3).toUpperCase()}
            </span>
            <div style={{ flex:1, height:4, background:'rgba(255,255,255,0.05)', borderRadius:2, overflow:'hidden' }}>
              <div style={{ width:`${(d.fastest_lap_ms??0)/best*100}%`, height:'100%',
                background: colour, borderRadius:2 }} />
            </div>
            <span style={{ fontFamily:'monospace', fontSize:10, color: i===0?'#FFD700':colour, width:62, textAlign:'right' }}>
              {lapStr}
            </span>
            {gap && <span style={{ fontFamily:'monospace', fontSize:9, color:'#3d4f66', width:44, textAlign:'right' }}>{gap}</span>}
          </div>
        )
      })}
    </div>
  )
}


const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8011'

function PanelBox({ title, badge, children, style = {} }) {
  return (
    <div style={{
      background: '#0d1018', border: '1px solid #1e2535',
      borderRadius: 6, display: 'flex', flexDirection: 'column',
      overflow: 'hidden', ...style,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '6px 12px', borderBottom: '1px solid #1e2535',
        background: '#0a0d14', flexShrink: 0,
      }}>
        <span className="font-mono text-xs tracking-widest uppercase" style={{ color: '#3d4f66' }}>
          {title}
        </span>
        {badge && (
          <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#E8002D',
            background: 'rgba(232,0,45,0.1)', padding: '2px 6px', borderRadius: 2 }}>
            {badge}
          </span>
        )}
      </div>
      <div style={{ flex: 1, overflow: 'hidden' }}>{children}</div>
    </div>
  )
}

function Select({ value, onChange, options, placeholder, disabled }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  const label = options.find(o => String(o.value) === String(value))?.label ?? placeholder
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <div
        onClick={() => !disabled && setOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '5px 10px', background: '#0d1018', border: '1px solid #1e2535',
          borderRadius: 4, cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.4 : 1,
        }}
      >
        <span style={{ fontFamily: 'monospace', fontSize: 11, color: value ? '#fff' : '#3d4f66' }}>
          {label}
        </span>
        <ChevronDown size={12} style={{ color: '#3d4f66', transform: open ? 'rotate(180deg)' : 'none',
          transition: 'transform 0.15s' }} />
      </div>
      {open && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
          background: '#0d1018', border: '1px solid #1e2535', borderTop: 'none',
          borderRadius: '0 0 4px 4px', maxHeight: 200, overflowY: 'auto',
        }}>
          {options.map(o => (
            <div key={o.value}
              onClick={() => { onChange(o.value); setOpen(false) }}
              style={{
                padding: '6px 10px', fontFamily: 'monospace', fontSize: 11,
                color: String(o.value) === String(value) ? '#E8002D' : '#8899aa',
                cursor: 'pointer', background: String(o.value) === String(value)
                  ? 'rgba(232,0,45,0.08)' : 'transparent',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
              onMouseLeave={e => e.currentTarget.style.background = String(o.value) === String(value)
                ? 'rgba(232,0,45,0.08)' : 'transparent'}
            >
              {o.label}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function RaceControl() {
  const { year: paramYear, gp: paramGp } = useParams()
  const navigate = useNavigate()

  // Sanitize URL params — fall back to empty string if invalid so the
  // dropdown still works rather than throwing to the error boundary.
  const safeParamYear = (() => { try { return String(sanitizeYear(paramYear)) } catch { return '' } })()
  const safeParamGp   = (() => { try { return sanitizeGP(paramGp)            } catch { return '' } })()

  const [years, setYears]   = useState([])
  const [year, setYear]     = useState(safeParamYear)
  const [events, setEvents] = useState([])
  const [gp, setGp]         = useState(safeParamGp)
  const [data, setData]     = useState(null)
  const [liveSession, setLiveSession] = useState(null)  // for detecting practice sessions
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState(null)

  // Load years
  useEffect(() => {
    fetch(`${API_BASE}/years`)
      .then(r => r.json())
      .then(d => {
        const yrs = d.years || []
        setYears(yrs)
        if (!year && yrs.length) setYear(String(yrs[yrs.length - 1]))
      })
      .catch(() => {})
  }, [])

  // Load events when year changes
  useEffect(() => {
    if (!year) return
    fetch(`${API_BASE}/schedule?year=${year}`)
      .then(r => r.json())
      .then(d => {
        const evts = d.events || []
        setEvents(evts)
        if (!gp && evts.length) setGp(evts[0])
      })
      .catch(() => setEvents([]))
  }, [year])

  // Load prediction when year+gp set
  useEffect(() => {
    if (!year || !gp) return
    setLoading(true)
    setError(null)
    navigate(`/race/${year}/${encodeURIComponent(gp)}`, { replace: true })
    fetch(`${API_BASE}/winner-probabilities?year=${year}&gp=${encodeURIComponent(gp)}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError('Failed to load predictions'); setLoading(false) })
  }, [year, gp])

  // Fetch live-status to know if we're in a practice session
  useEffect(() => {
    fetch(`${API_BASE}/live-status`).then(r=>r.json()).then(setLiveSession).catch(()=>{})
    const id = setInterval(() => {
      fetch(`${API_BASE}/live-status`).then(r=>r.json()).then(setLiveSession).catch(()=>{})
    }, 30000)
    return () => clearInterval(id)
  }, [])

  const isPractice = ['FP1','FP2','FP3','Practice'].includes(liveSession?.session_type?.toUpperCase?.() ?? '')
  const drivers  = data?.predictions || []
  const chaos    = data?.chaos_index ?? 0
  const scRate   = data?.sc_rate ?? 0
  const hasPrac  = data?.has_practice_data ?? false
  const top1     = drivers[0]

  return (
    <div style={{ minHeight: '100vh', background: '#080c12', display: 'flex', flexDirection: 'column' }}>
      <StatusBanner year={year} gp={gp} />

      {/* Selector bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 16px',
        borderBottom: '1px solid #1e2535', background: '#0a0d14', flexShrink: 0 }}>
        <span className="font-mono text-xs tracking-widest" style={{ color: '#3d4f66' }}>SELECT RACE</span>
        <div style={{ width: 120 }}>
          <Select value={year} onChange={v => { setYear(v); setGp('') }}
            options={years.map(y => ({ value: y, label: String(y) }))}
            placeholder="YEAR" disabled={years.length === 0} />
        </div>
        <div style={{ width: 240 }}>
          <Select value={gp} onChange={setGp}
            options={events.map(e => ({ value: e, label: e.replace(' Grand Prix', ' GP') }))}
            placeholder={year ? 'GRAND PRIX' : '---'} disabled={!year || events.length === 0} />
        </div>
        {loading && <RefreshCw size={12} style={{ color: '#3d4f66', animation: 'spin 1s linear infinite' }} />}
        {hasPrac && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 5,
            background: 'rgba(0,255,136,0.08)', border: '1px solid rgba(0,255,136,0.2)',
            borderRadius: 4, padding: '3px 8px' }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#00ff88' }} />
            <span className="font-mono text-xs" style={{ color: '#00ff88' }}>PRACTICE DATA</span>
          </div>
        )}
      </div>

      {/* Main multi-viewer grid */}
      <div style={{ flex: 1, display: 'grid', padding: 10, gap: 8,
        gridTemplateColumns: '280px 1fr 260px', gridTemplateRows: '1fr auto',
        minHeight: 0 }}>

        {/* LEFT: Leaderboard */}
        <PanelBox title="PREDICTION TOWER" badge={isPractice ? (liveSession?.session_type || "PRACTICE") : `${drivers.length} DRIVERS`}
          style={{ gridRow: '1', gridColumn: '1' }}>
          {isPractice
            ? <PracticeLeaderboard drivers={
                // derive from live leaderboard state if available
                (liveSession?.leaderboard || []).map((d,i,arr) => ({
                  driver: d.driver_code || d.name_acronym || d.Driver,
                  team:   d.team || '',
                  fastest_lap_ms: d.last_lap_ms ?? null,
                  gap_ms: i===0 ? 0 : d.gap_to_leader_ms ?? null,
                })).filter(d=>d.driver)
              } />
            : <LeaderBoard drivers={drivers} loading={loading} />
          }
        </PanelBox>

        {/* CENTRE: Circuit map */}
        <PanelBox title={gp ? gp.replace(' Grand Prix', ' GP').toUpperCase() : 'CIRCUIT MAP'}
          badge={year || undefined} style={{ gridRow: '1', gridColumn: '2' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', height: '100%', gap: 16, padding: 16 }}>
            <CircuitMap gpName={gp} drivers={drivers} width={320} height={280} />
            {/* P1 highlight */}
            {top1 && (
              <div style={{ textAlign: 'center' }}>
                <div className="font-mono text-xs tracking-widest" style={{ color: '#3d4f66', marginBottom: 4 }}>
                  PREDICTED WINNER
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center' }}>
                  <div style={{ width: 10, height: 10, borderRadius: '50%',
                    background: getTeamColour(top1.team || top1.Team || ''),
                    boxShadow: `0 0 10px ${getTeamColour(top1.team || top1.Team || '')}` }} />
                  <span className="font-mono font-bold text-white" style={{ fontSize: 18, letterSpacing: 4 }}>
                    {(top1.driver || top1.Driver || '').slice(0, 3).toUpperCase()}
                  </span>
                  <span className="font-mono font-bold" style={{ fontSize: 18, color: '#E8002D' }}>
                    {((top1.likely_probability ?? top1.probability ?? 0) * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="font-mono text-xs" style={{ color: '#3d4f66', marginTop: 2 }}>
                  {top1.team || top1.Team || ''}
                </div>
              </div>
            )}
          </div>
        </PanelBox>

        {/* RIGHT: Chaos + scenario */}
        <div style={{ gridRow: '1', gridColumn: '3', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <PanelBox title="CHAOS INDEX" style={{ flexShrink: 0 }}>
            <ChaosDisplay chaosIndex={chaos} scRate={scRate} hasPracticeData={hasPrac} />
          </PanelBox>

          <PanelBox title="TOP 3 SCENARIOS" style={{ flex: 1 }}>
            <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {drivers.slice(0, 3).map((d, i) => {
                const colour = getTeamColour(d.team || d.Team || '')
                const likely = (d.likely_probability ?? d.probability ?? 0) * 100
                const best   = (d.scenarios?.best_case ?? 0) * 100
                const worst  = (d.scenarios?.worst_case ?? 0) * 100
                return (
                  <div key={d.driver || i} style={{ background: 'rgba(255,255,255,0.03)',
                    borderRadius: 4, padding: '8px 10px', borderLeft: `3px solid ${colour}` }}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono font-bold text-white" style={{ fontSize: 12 }}>
                        P{i+1} {(d.driver || d.Driver || '').slice(0,3).toUpperCase()}
                      </span>
                      <span className="font-mono font-bold" style={{ fontSize: 13, color: colour }}>
                        {likely.toFixed(1)}%
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: 4, height: 4, borderRadius: 2, overflow: 'hidden',
                      background: 'rgba(255,255,255,0.06)' }}>
                      <div style={{ width: `${worst}%`, background: `${colour}55` }} />
                      <div style={{ width: `${likely - worst}%`, background: colour }} />
                      <div style={{ width: `${best - likely}%`, background: `${colour}88` }} />
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="font-mono" style={{ fontSize: 8, color: '#3d4f66' }}>
                        ↓{worst.toFixed(0)}%
                      </span>
                      <span className="font-mono" style={{ fontSize: 8, color: '#3d4f66' }}>
                        ↑{best.toFixed(0)}%
                      </span>
                    </div>
                  </div>
                )
              })}
              {drivers.length === 0 && !loading && (
                <div className="font-mono text-xs text-center" style={{ color: '#3d4f66', marginTop: 24 }}>
                  SELECT A RACE
                </div>
              )}
            </div>
          </PanelBox>
        </div>

        {/* BOTTOM: Quick stats strip */}
        <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 8 }}>
          {[
            { label: 'CHAOS', value: chaos.toFixed(2), colour: chaos > 0.7 ? '#E8002D' : chaos > 0.4 ? '#FFD700' : '#00ff88' },
            { label: 'SC PROB', value: `${Math.round(scRate * 100)}%`, colour: '#FF8000' },
            { label: 'DRIVERS', value: drivers.length, colour: '#64C4FF' },
            { label: 'TOP PICK', value: drivers[0] ? (drivers[0].driver || drivers[0].Driver || '').slice(0,3).toUpperCase() : '--', colour: '#fff' },
            { label: 'BEST ODDS', value: drivers[0] ? `${((drivers[0].scenarios?.best_case ?? 0)*100).toFixed(1)}%` : '--', colour: '#00ff88' },
            { label: 'WORST ODDS', value: drivers[0] ? `${((drivers[0].scenarios?.worst_case ?? 0)*100).toFixed(1)}%` : '--', colour: '#E8002D' },
          ].map(({ label, value, colour }) => (
            <div key={label} style={{ flex: 1, background: '#0d1018', border: '1px solid #1e2535',
              borderRadius: 4, padding: '8px 12px' }}>
              <div className="font-mono text-xs" style={{ color: '#3d4f66', marginBottom: 2 }}>{label}</div>
              <div className="font-mono font-bold" style={{ fontSize: 16, color: colour }}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div style={{ position: 'fixed', bottom: 16, left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(232,0,45,0.15)', border: '1px solid #E8002D', borderRadius: 6,
          padding: '8px 16px', display: 'flex', gap: 8, alignItems: 'center' }}>
          <AlertTriangle size={14} style={{ color: '#E8002D' }} />
          <span className="font-mono text-xs" style={{ color: '#E8002D' }}>{error}</span>
        </div>
      )}
    </div>
  )
}
