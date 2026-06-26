import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { User, TrendingUp, Target, Award } from 'lucide-react'
import StatusBanner from '../components/StatusBanner'
import { getTeamColour } from '../components/TeamColours'
import { parseRouteParams } from '../utils/sanitizeParams'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8011'

function ScenarioBar({ best, likely, worst, colour }) {
  const [loaded, setLoaded] = useState(false)
  useEffect(() => { const t = setTimeout(() => setLoaded(true), 100); return () => clearTimeout(t) }, [])
  return (
    <div style={{ position: 'relative', height: 12, background: 'rgba(255,255,255,0.06)',
      borderRadius: 6, overflow: 'hidden' }}>
      {/* Best case (faint) */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0,
        width: loaded ? `${best * 100}%` : '0%',
        background: `${colour}22`, transition: 'width 800ms ease-out', borderRadius: 6 }} />
      {/* Likely (solid) */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0,
        width: loaded ? `${likely * 100}%` : '0%',
        background: colour, transition: 'width 600ms ease-out', borderRadius: 6,
        boxShadow: `0 0 10px ${colour}66` }} />
    </div>
  )
}

function StatCard({ icon: Icon, label, value, sub, colour = '#8899aa' }) {
  return (
    <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6, padding: '10px 14px' }}>
      <div className="flex items-center gap-2 mb-2">
        <Icon size={11} style={{ color: colour }} />
        <span className="font-mono text-xs tracking-widest uppercase" style={{ color: '#3d4f66' }}>{label}</span>
      </div>
      <div className="font-mono font-bold" style={{ fontSize: 20, color: colour }}>{value}</div>
      {sub && <div className="font-mono text-xs" style={{ color: '#3d4f66', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function FeatureRow({ label, value, max = 1, colour = '#3671C6', format = v => v }) {
  const pct = max > 0 ? Math.min(1, Math.abs(value) / max) : 0
  return (
    <div style={{ marginBottom: 10 }}>
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>{label}</span>
        <span className="font-mono text-xs font-bold" style={{ color: colour }}>{format(value)}</span>
      </div>
      <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct * 100}%`, height: '100%', background: colour, borderRadius: 2,
          transition: 'width 600ms ease-out' }} />
      </div>
    </div>
  )
}

export default function DriverIntel() {
  const rawParams = useParams()
  const { year, gp: gpDecoded } = parseRouteParams(rawParams)

  const [data, setData]         = useState(null)
  const [loading, setLoading]   = useState(false)
  const [selected, setSelected] = useState('')

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

  const drivers  = data?.predictions || []
  const driver   = drivers.find(d => (d.driver || d.Driver) === selected) || drivers[0]
  const leader   = drivers[0]
  const colour   = driver ? getTeamColour(driver.team || driver.Team || '') : '#8899aa'
  const lColour  = leader ? getTeamColour(leader.team || leader.Team || '') : '#8899aa'

  const likely  = driver?.likely_probability ?? driver?.probability ?? 0
  const best    = driver?.scenarios?.best_case ?? likely
  const worst   = driver?.scenarios?.worst_case ?? likely
  const gridPos = driver?.grid_position ?? driver?.GridPosition ?? null
  const qualiGap = driver?.qualifying_time_gap ?? driver?.QualiTimeGap ?? null
  const winRate  = driver?.driver_win_rate ?? driver?.DriverWinRate ?? null
  const avgPos   = driver?.driver_avg_position ?? driver?.DriverAvgPosition ?? null
  const team     = driver?.team || driver?.Team || ''
  const name     = driver?.driver || driver?.Driver || ''

  const lLikely  = leader?.likely_probability ?? leader?.probability ?? 0
  const probGap  = leader && driver && leader !== driver
    ? (lLikely - likely) * 100 : 0

  return (
    <div style={{ minHeight: '100vh', background: '#080c12', display: 'flex', flexDirection: 'column' }}>
      <StatusBanner year={year} gp={gpDecoded} />

      <div style={{ flex: 1, display: 'grid', padding: 10, gap: 8,
        gridTemplateColumns: '220px 1fr', gridTemplateRows: 'auto 1fr' }}>

        {/* Driver selector */}
        <div style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: 8,
          background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6, padding: '8px 12px' }}>
          <User size={12} style={{ color: '#3d4f66' }} />
          <span className="font-mono text-xs tracking-widest" style={{ color: '#3d4f66' }}>DRIVER</span>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginLeft: 8 }}>
            {drivers.map((d, i) => {
              const dc = d.driver || d.Driver || ''
              const tc = getTeamColour(d.team || d.Team || '')
              const active = dc === selected
              return (
                <button key={dc}
                  onClick={() => setSelected(dc)}
                  style={{
                    padding: '4px 10px', borderRadius: 4, cursor: 'pointer',
                    fontFamily: 'monospace', fontSize: 10, fontWeight: 700,
                    border: `1px solid ${active ? tc : '#1e2535'}`,
                    background: active ? `${tc}22` : 'transparent',
                    color: active ? tc : '#3d4f66',
                    transition: 'all 0.15s',
                  }}>
                  {dc.slice(0, 3).toUpperCase()}
                </button>
              )
            })}
          </div>
        </div>

        {/* Left: driver header + stats */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Driver identity card */}
          <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
            padding: '14px 16px', borderLeft: `4px solid ${colour}` }}>
            <div className="font-mono text-xs tracking-widest mb-1" style={{ color: '#3d4f66' }}>
              {team.toUpperCase()}
            </div>
            <div className="font-mono font-bold text-white" style={{ fontSize: 28, letterSpacing: 4 }}>
              {name.slice(0, 3).toUpperCase()}
            </div>
            <div className="font-mono text-xs" style={{ color: colour, marginTop: 2 }}>{name}</div>
            <div className="flex items-center gap-8 mt-3">
              <div>
                <div className="font-mono text-xs" style={{ color: '#3d4f66' }}>LIKELY</div>
                <div className="font-mono font-bold" style={{ fontSize: 18, color: colour }}>
                  {(likely * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="font-mono text-xs" style={{ color: '#3d4f66' }}>BEST</div>
                <div className="font-mono font-bold" style={{ fontSize: 14, color: '#00ff88' }}>
                  {(best * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="font-mono text-xs" style={{ color: '#3d4f66' }}>WORST</div>
                <div className="font-mono font-bold" style={{ fontSize: 14, color: '#E8002D' }}>
                  {(worst * 100).toFixed(1)}%
                </div>
              </div>
            </div>
            <div style={{ marginTop: 10 }}>
              <ScenarioBar best={best} likely={likely} worst={worst} colour={colour} />
              <div className="flex justify-between mt-1">
                <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>WORST</span>
                <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>LIKELY</span>
                <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>BEST</span>
              </div>
            </div>
          </div>

          {/* Quick stats */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <StatCard icon={Target}    label="Grid Pos" value={gridPos != null ? `P${gridPos}` : '--'} colour={colour} />
            <StatCard icon={TrendingUp} label="Win Rate" value={winRate != null ? `${(winRate * 100).toFixed(0)}%` : '--'}
              colour={colour} sub="this season" />
            <StatCard icon={Award}     label="Avg Pos"  value={avgPos != null ? avgPos.toFixed(1) : '--'}
              colour={colour} sub="this season" />
            <StatCard icon={User}      label="Quali Gap" value={qualiGap != null ? `+${qualiGap.toFixed(3)}s` : '--'}
              colour={colour} sub="to pole" />
          </div>
        </div>

        {/* Right: feature breakdown + head-to-head */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Feature breakdown */}
          <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
            padding: '12px 14px', flex: 1 }}>
            <div className="font-mono text-xs tracking-widest mb-4" style={{ color: '#3d4f66' }}>
              FEATURE BREAKDOWN
            </div>
            <FeatureRow label="Win Probability (Likely)"   value={likely} max={0.5}   colour={colour}
              format={v => `${(v*100).toFixed(1)}%`} />
            <FeatureRow label="Best Case Scenario"         value={best}   max={0.5}   colour="#00ff88"
              format={v => `${(v*100).toFixed(1)}%`} />
            <FeatureRow label="Worst Case Scenario"        value={worst}  max={0.5}   colour="#E8002D"
              format={v => `${(v*100).toFixed(1)}%`} />
            {gridPos != null && (
              <FeatureRow label="Grid Position (inverted)" value={Math.max(0, 21 - gridPos)} max={20}
                colour={colour} format={v => `P${21 - Math.max(0, v)}`} />
            )}
            {qualiGap != null && (
              <FeatureRow label="Qualifying Gap to Pole"   value={Math.max(0, 3 - qualiGap)} max={3}
                colour="#FF8000" format={() => `+${qualiGap.toFixed(3)}s`} />
            )}
            {winRate != null && (
              <FeatureRow label="Season Win Rate"          value={winRate} max={1}    colour="#27F4D2"
                format={v => `${(v*100).toFixed(0)}%`} />
            )}
            {avgPos != null && (
              <FeatureRow label="Avg Finishing Position"   value={Math.max(0, 21 - avgPos)} max={20}
                colour="#64C4FF" format={() => avgPos.toFixed(1)} />
            )}
          </div>

          {/* Head-to-head vs leader */}
          {leader && driver && leader !== driver && (
            <div style={{ background: '#0d1018', border: '1px solid #1e2535', borderRadius: 6,
              padding: '12px 14px' }}>
              <div className="font-mono text-xs tracking-widest mb-3" style={{ color: '#3d4f66' }}>
                HEAD TO HEAD vs LEADER
              </div>
              <div className="flex items-center gap-4">
                <div style={{ flex: 1, textAlign: 'center' }}>
                  <div className="font-mono font-bold" style={{ fontSize: 20, color: colour, letterSpacing: 3 }}>
                    {name.slice(0, 3).toUpperCase()}
                  </div>
                  <div className="font-mono text-xs" style={{ color: '#3d4f66' }}>{team}</div>
                  <div className="font-mono font-bold" style={{ fontSize: 16, color: colour, marginTop: 4 }}>
                    {(likely * 100).toFixed(1)}%
                  </div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div className="font-mono text-xs" style={{ color: '#3d4f66', marginBottom: 4 }}>GAP</div>
                  <div className="font-mono font-bold" style={{ fontSize: 14, color: '#E8002D' }}>
                    -{probGap.toFixed(1)}pp
                  </div>
                </div>
                <div style={{ flex: 1, textAlign: 'center' }}>
                  <div className="font-mono font-bold" style={{ fontSize: 20, color: lColour, letterSpacing: 3 }}>
                    {(leader.driver || leader.Driver || '').slice(0, 3).toUpperCase()}
                  </div>
                  <div className="font-mono text-xs" style={{ color: '#3d4f66' }}>
                    {leader.team || leader.Team || ''}
                  </div>
                  <div className="font-mono font-bold" style={{ fontSize: 16, color: lColour, marginTop: 4 }}>
                    {(lLikely * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
